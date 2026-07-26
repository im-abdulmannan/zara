import { useEffect, useMemo, useState } from "react";
import {
  api,
  Connection,
  isFreeModel,
  LiveStatus,
  Profile,
  ProviderPreset,
} from "./api";

type Tab = "provider" | "intent" | "profile";

export default function App() {
  const [tab, setTab] = useState<Tab>("provider");
  const [status, setStatus] = useState<LiveStatus>({
    state: "idle",
    subtitle: 'Say "Hey Zara" to start...',
    active_model: "",
  });
  const [presets, setPresets] = useState<ProviderPreset[]>([]);
  const [connection, setConnection] = useState<Connection | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [providers, conn] = await Promise.all([api.providers(), api.connection()]);
        if (cancelled) return;
        setPresets(providers.presets);
        setConnection(conn);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(async () => {
      try {
        setStatus(await api.status());
      } catch {
        /* voice loop may not be up yet */
      }
    }, 700);
    return () => window.clearInterval(timer);
  }, []);

  const listening = /listen|record|wake|speak/i.test(status.state);
  const modelLabel = status.active_model || connection?.active_summary || "No model selected";

  return (
    <div className="app">
      <header className="hero">
        <div className="brand-block">
          <h1 className="brand">Zara</h1>
          <span className="brand-tag">Voice assistant</span>
        </div>
        <div className="live">
          <div className="live-row">
            <span className={`pulse ${listening ? "live" : ""}`} />
            <span className="badge">{status.state}</span>
          </div>
          <p className="subtitle">{status.subtitle}</p>
        </div>
        <div className="model-chip" title={modelLabel}>
          <strong>Active model</strong>
          {modelLabel}
        </div>
      </header>

      <nav className="tabs" aria-label="Settings">
        {(
          [
            ["provider", "Provider"],
            ["intent", "Intent"],
            ["profile", "Profile"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            className={`tab ${tab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      {error ? <p className="error">{error}</p> : null}

      <main className="panel">
        {tab === "provider" && connection ? (
          <ProviderTab
            presets={presets}
            connection={connection}
            busy={busy}
            setBusy={setBusy}
            setError={setError}
            onSaved={setConnection}
          />
        ) : null}
        {tab === "intent" && connection ? (
          <IntentTab
            presets={presets}
            connection={connection}
            busy={busy}
            setBusy={setBusy}
            setError={setError}
            onSaved={setConnection}
          />
        ) : null}
        {tab === "profile" ? (
          <ProfileTab setError={setError} busy={busy} setBusy={setBusy} />
        ) : null}
      </main>
    </div>
  );
}

function ProviderTab({
  presets,
  connection,
  busy,
  setBusy,
  setError,
  onSaved,
}: {
  presets: ProviderPreset[];
  connection: Connection;
  busy: boolean;
  setBusy: (v: boolean) => void;
  setError: (v: string) => void;
  onSaved: (c: Connection) => void;
}) {
  const [providerId, setProviderId] = useState(connection.provider_id);
  const [baseUrl, setBaseUrl] = useState(connection.base_url);
  const [apiKey, setApiKey] = useState(connection.api_key);
  const [model, setModel] = useState(connection.model);
  const [models, setModels] = useState<string[]>([]);
  const [freeOnly, setFreeOnly] = useState(false);
  const [manual, setManual] = useState(connection.model);
  const [message, setMessage] = useState("");
  const [loadingModels, setLoadingModels] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(
    connection.provider_id === "custom" || !connection.base_url,
  );

  const preset = useMemo(
    () => presets.find((p) => p.id === providerId) || null,
    [presets, providerId],
  );

  const keyRequired = !(preset?.allow_empty_key);
  const keyReady = Boolean(apiKey.trim()) || !keyRequired;
  const visible = freeOnly ? models.filter(isFreeModel) : models;

  // After the user pastes/types an API key, fetch that provider's models.
  useEffect(() => {
    const url = baseUrl.trim();
    const key = apiKey.trim();

    if (!url) {
      setModels([]);
      setMessage(
        providerId === "custom"
          ? "Enter the Base URL for your LLM, then paste the API key."
          : "Select a provider, then paste its API key.",
      );
      return;
    }

    if (keyRequired && !key) {
      setModels([]);
      setLoadingModels(false);
      setMessage(`Paste your ${preset?.label || "provider"} API key to load models.`);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoadingModels(true);
      setError("");
      setMessage(`Loading models for ${preset?.label || "provider"}…`);
      api
        .fetchModels(url, key || preset?.default_api_key || "")
        .then((result) => {
          if (cancelled) return;
          setModels(result.models);
          setMessage(
            result.models.length
              ? `Loaded ${result.models.length} models. Pick one and save.`
              : "Provider returned no models for this key.",
          );
        })
        .catch((err) => {
          if (cancelled) return;
          setModels([]);
          setMessage(err instanceof Error ? err.message : String(err));
        })
        .finally(() => {
          if (!cancelled) setLoadingModels(false);
        });
    }, 450);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [providerId, baseUrl, apiKey, keyRequired, preset?.label, preset?.default_api_key, setError]);

  function selectProvider(id: string) {
    const next = presets.find((p) => p.id === id);
    setProviderId(id);
    setModels([]);
    setModel("");
    setManual("");
    if (!next) return;

    if (next.base_url) setBaseUrl(next.base_url);
    setShowAdvanced(id === "custom" || !next.base_url);

    // Switching LLM → ask for that provider's key (keep only if same provider reload).
    if (id !== connection.provider_id) {
      setApiKey(next.default_api_key || "");
      setMessage(
        next.allow_empty_key
          ? `Selected ${next.label}. Loading local models…`
          : `Selected ${next.label}. Paste the API key to load models.`,
      );
    } else {
      setApiKey(connection.api_key || next.default_api_key || "");
      setModel(connection.model);
      setManual(connection.model);
    }
  }

  async function testConn() {
    setBusy(true);
    setError("");
    try {
      const result = await api.testConnection(baseUrl, apiKey, model);
      setMessage(`Connection OK: ${result.reply}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      const saved = await api.saveProvider({
        provider_id: providerId,
        base_url: baseUrl,
        api_key: apiKey,
        model,
      });
      onSaved(saved);
      setMessage("Provider saved and applied.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const step = !providerId ? 1 : !keyReady ? 2 : !model ? 3 : 4;

  return (
    <div className="stack">
      <div className="page-head">
        <h2>Connect your LLM</h2>
        <p>Choose a provider, paste its API key, then pick a live model for Zara to use.</p>
      </div>

      <div className="steps" aria-hidden="true">
        <span className={`step ${step >= 1 ? "on" : ""}`}><span className="n">1</span> LLM</span>
        <span className={`step ${step >= 2 ? "on" : ""}`}><span className="n">2</span> API key</span>
        <span className={`step ${step >= 3 ? "on" : ""}`}><span className="n">3</span> Model</span>
        <span className={`step ${step >= 4 ? "on" : ""}`}><span className="n">4</span> Save</span>
      </div>

      <section className="section">
        <p className="section-title">Provider</p>
        <div className="field">
          <label>LLM</label>
          <select value={providerId} onChange={(e) => selectProvider(e.target.value)}>
            {presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>API key {keyRequired ? "" : "(optional for local)"}</label>
          <input
            type="password"
            value={apiKey}
            autoComplete="off"
            placeholder={preset?.api_key_placeholder || "Paste API key"}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>

        {(showAdvanced || providerId === "custom") && (
          <div className="field">
            <label>Base URL</label>
            <input
              value={baseUrl}
              placeholder="https://api.example.com/v1"
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </div>
        )}

        {providerId !== "custom" && preset?.base_url ? (
          <button className="btn linkish" type="button" onClick={() => setShowAdvanced((v) => !v)}>
            {showAdvanced ? "Hide Base URL" : "Edit Base URL"}
          </button>
        ) : null}
      </section>

      {!keyReady ? (
        <div className="gate">
          <p>
            Paste your <strong>{preset?.label || "provider"}</strong> API key.
            Matching models will appear here automatically.
          </p>
        </div>
      ) : (
        <section className="section">
          <div className="row push">
            <p className="section-title">Models</p>
            <label className="check">
              <input
                type="checkbox"
                checked={freeOnly}
                onChange={(e) => setFreeOnly(e.target.checked)}
              />
              Free only
            </label>
          </div>

          {loadingModels ? <div className="loading-bar" /> : null}

          <div className="selected-pill">
            Selected <b>{model || "none yet"}</b>
          </div>

          <div className="field">
            <label>Or type a model ID</label>
            <input
              value={manual}
              onChange={(e) => {
                setManual(e.target.value);
                setModel(e.target.value.trim());
              }}
            />
          </div>

          {visible.length ? (
            <div className="model-grid">
              {visible.map((id) => (
                <button
                  key={id}
                  type="button"
                  className={`model-card ${model === id ? "selected" : ""}`}
                  onClick={() => {
                    setModel(id);
                    setManual(id);
                  }}
                >
                  <strong>{id}</strong>
                  <span className={isFreeModel(id) ? "free" : ""}>
                    {isFreeModel(id) ? "FREE" : "MODEL"}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty">
              {loadingModels
                ? "Fetching models…"
                : models.length
                  ? "No free models in this list. Turn off Free only."
                  : "No models returned. Check the API key."}
            </div>
          )}
          <p className="status-line">{message}</p>
        </section>
      )}

      <div className="actions">
        <button
          className="btn"
          type="button"
          disabled={busy || !keyReady || !model}
          onClick={testConn}
        >
          Test connection
        </button>
        <button
          className="btn primary"
          type="button"
          disabled={busy || !keyReady || !model}
          onClick={save}
        >
          Save provider
        </button>
      </div>
    </div>
  );
}

function IntentTab({
  presets,
  connection,
  busy,
  setBusy,
  setError,
  onSaved,
}: {
  presets: ProviderPreset[];
  connection: Connection;
  busy: boolean;
  setBusy: (v: boolean) => void;
  setError: (v: string) => void;
  onSaved: (c: Connection) => void;
}) {
  const [enabled, setEnabled] = useState(connection.intent_enabled);
  const [backend, setBackend] = useState(connection.intent_backend || "gemini");
  const [providerId, setProviderId] = useState(
    connection.intent_provider_id || connection.provider_id || "openrouter",
  );
  const [baseUrl, setBaseUrl] = useState(
    connection.intent_base_url || connection.base_url || "",
  );
  const [apiKey, setApiKey] = useState(
    connection.intent_api_key || connection.api_key || "",
  );
  const [confidence, setConfidence] = useState(connection.intent_confidence);
  const [model, setModel] = useState(connection.intent_model || "");
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [freeOnly, setFreeOnly] = useState(false);
  const [manual, setManual] = useState(connection.intent_model || "");
  const [message, setMessage] = useState("");

  const geminiPreset = presets.find((p) => p.id === "gemini");
  const intentPreset = presets.find((p) => p.id === providerId);
  const fetchUrl =
    backend === "gemini"
      ? (baseUrl.trim() || geminiPreset?.base_url || "").trim()
      : baseUrl.trim();
  const keyRequired = backend === "gemini"
    ? true
    : !intentPreset?.allow_empty_key;
  const keyReady = !keyRequired || Boolean(apiKey.trim());

  useEffect(() => {
    if (!enabled || !keyReady || !fetchUrl) {
      setModels([]);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoadingModels(true);
      setMessage("Fetching models with your API key…");
      api
        .fetchModels(fetchUrl, apiKey)
        .then((result) => {
          if (cancelled) return;
          const next = [...result.models];
          const selected = model.trim();
          if (selected && !next.includes(selected)) next.unshift(selected);
          setModels(next);
          setMessage(
            result.models.length
              ? `Loaded ${result.models.length} models. Pick one and save.`
              : "No models returned. Check the API key.",
          );
        })
        .catch((err) => {
          if (cancelled) return;
          setModels([]);
          setMessage(err instanceof Error ? err.message : String(err));
        })
        .finally(() => {
          if (!cancelled) setLoadingModels(false);
        });
    }, 450);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backend, providerId, fetchUrl, enabled, keyReady, apiKey]);

  const visible = freeOnly ? models.filter(isFreeModel) : models;

  async function persist(nextEnabled: boolean, withDetails = false) {
    setBusy(true);
    setError("");
    try {
      const saved = await api.saveIntent({
        intent_enabled: nextEnabled,
        intent_backend: backend,
        intent_provider_id: providerId,
        intent_base_url: backend === "gemini" ? fetchUrl : baseUrl,
        intent_api_key: apiKey,
        intent_model: model,
        intent_confidence: confidence,
        validate_details: withDetails && nextEnabled,
      });
      setEnabled(nextEnabled);
      onSaved(saved);
      setMessage(
        nextEnabled
          ? withDetails
            ? "Intent details saved."
            : "Intent enabled. Paste an API key to load models."
          : "Intent disabled.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function fetchModels() {
    if (!fetchUrl) {
      setError("Base URL is required to fetch models.");
      return;
    }
    setBusy(true);
    setLoadingModels(true);
    setError("");
    try {
      const result = await api.fetchModels(fetchUrl, apiKey);
      setModels(result.models);
      setMessage(`Loaded ${result.models.length} intent models.`);
    } catch (err) {
      setModels([]);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      setLoadingModels(false);
    }
  }

  if (!enabled) {
    return (
      <div className="stack">
        <div className="page-head">
          <h2>Intent routing</h2>
          <p>Optional fast path for clear commands before the main chat model.</p>
        </div>
        <div className="gate">
          <p>
            Enable Intent to classify reminders, open-app, and search requests quickly.
            You can turn it off anytime.
          </p>
          <div className="row" style={{ marginTop: 18 }}>
            <button
              className="btn primary"
              type="button"
              disabled={busy}
              onClick={() => persist(true)}
            >
              Enable Intent
            </button>
            <button
              className="btn"
              type="button"
              disabled={busy}
              onClick={() => persist(false)}
            >
              Keep disabled
            </button>
          </div>
        </div>
        <p className="status-line">{message}</p>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div className="row push">
          <h2>Intent routing</h2>
          <button className="btn" type="button" disabled={busy} onClick={() => persist(false)}>
            Disable
          </button>
        </div>
        <p>
          Paste an API key, fetch live models, then save. No preset model list.
          Low-confidence requests still fall back to chat.
        </p>
      </div>

      <section className="section">
        <div className="row push">
          <p className="section-title">Connection</p>
          <button
            className="btn linkish"
            type="button"
            disabled={busy}
            onClick={() => {
              setBackend("openai");
              setProviderId(connection.provider_id);
              setBaseUrl(connection.base_url);
              setApiKey(connection.api_key);
              setModel("");
              setManual("");
              setModels([]);
              setMessage("Copied your main Provider endpoint. Models will load from the key.");
            }}
          >
            Use my main LLM
          </button>
        </div>
        <div className="field">
          <label>Backend</label>
          <select
            value={backend}
            onChange={(e) => {
              const next = e.target.value;
              setBackend(next);
              setModels([]);
              setModel("");
              setManual("");
              if (next === "gemini" && geminiPreset?.base_url) {
                setBaseUrl(geminiPreset.base_url);
              }
            }}
          >
            <option value="gemini">Gemini (Google AI)</option>
            <option value="openai">Any OpenAI-compatible LLM</option>
          </select>
        </div>

        {backend === "openai" ? (
          <>
            <div className="field">
              <label>Provider</label>
              <select
                value={providerId}
                onChange={(e) => {
                  const id = e.target.value;
                  setProviderId(id);
                  setModels([]);
                  setModel("");
                  setManual("");
                  const preset = presets.find((p) => p.id === id);
                  if (preset?.base_url) setBaseUrl(preset.base_url);
                  if (id !== connection.intent_provider_id) {
                    setApiKey(preset?.default_api_key || "");
                  }
                }}
              >
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Base URL</label>
              <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            </div>
          </>
        ) : null}

        <div className="field">
          <label>API key {keyRequired ? "" : "(optional for local)"}</label>
          <input
            type="password"
            value={apiKey}
            autoComplete="off"
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              backend === "gemini"
                ? geminiPreset?.api_key_placeholder || "Gemini API key"
                : intentPreset?.api_key_placeholder || "API key"
            }
          />
        </div>

        <div className="field">
          <label>Confidence threshold · {confidence.toFixed(2)}</label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={confidence}
            onChange={(e) => setConfidence(Number(e.target.value))}
          />
        </div>
      </section>

      {!keyReady ? (
        <div className="gate">
          <p>
            Paste your API key. Matching Intent models will load automatically — nothing is
            pre-listed.
          </p>
        </div>
      ) : (
        <section className="section">
          <div className="row push">
            <p className="section-title">Intent model</p>
            <label className="check">
              <input
                type="checkbox"
                checked={freeOnly}
                onChange={(e) => setFreeOnly(e.target.checked)}
              />
              Free only
            </label>
          </div>

          {loadingModels ? <div className="loading-bar" /> : null}

          <div className="selected-pill">
            Selected <b>{model || "none yet"}</b>
          </div>

          <div className="field">
            <label>Or type a model ID</label>
            <input
              value={manual}
              onChange={(e) => {
                setManual(e.target.value);
                setModel(e.target.value.trim());
              }}
            />
          </div>

          {visible.length ? (
            <div className="model-grid">
              {visible.map((id) => (
                <button
                  key={id}
                  type="button"
                  className={`model-card ${model === id ? "selected" : ""}`}
                  onClick={() => {
                    setModel(id);
                    setManual(id);
                  }}
                >
                  <strong>{id}</strong>
                  <span className={isFreeModel(id) ? "free" : ""}>
                    {isFreeModel(id) ? "FREE" : "MODEL"}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty">
              {loadingModels
                ? "Fetching models…"
                : models.length
                  ? "No free models in this list. Turn off Free only."
                  : "No models returned. Check the API key."}
            </div>
          )}

          <button className="btn linkish" type="button" disabled={busy || !keyReady} onClick={fetchModels}>
            Refresh models
          </button>
          <p className="status-line">{message}</p>
        </section>
      )}

      <div className="actions">
        <button
          className="btn primary"
          type="button"
          disabled={busy || !keyReady || !model}
          onClick={() => persist(true, true)}
        >
          Save Intent details
        </button>
      </div>
    </div>
  );
}

function ProfileTab({
  setError,
  busy,
  setBusy,
}: {
  setError: (v: string) => void;
  busy: boolean;
  setBusy: (v: boolean) => void;
}) {
  const [profile, setProfile] = useState<Profile>({ name: "", browser: "", notes: "" });
  const [message, setMessage] = useState("");

  useEffect(() => {
    api
      .profile()
      .then(setProfile)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [setError]);

  async function save() {
    setBusy(true);
    setError("");
    try {
      const saved = await api.saveProfile(profile);
      setProfile(saved);
      setMessage("Profile saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h2>Your profile</h2>
        <p>Personal details Zara keeps in local memory for natural replies.</p>
      </div>

      <section className="section">
        <p className="section-title">About you</p>
        <div className="field">
          <label>Name</label>
          <input
            value={profile.name}
            placeholder="How should Zara address you?"
            onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))}
          />
        </div>
        <div className="field">
          <label>Preferred browser</label>
          <input
            value={profile.browser}
            placeholder="chrome, edge…"
            onChange={(e) => setProfile((p) => ({ ...p, browser: e.target.value }))}
          />
        </div>
        <div className="field">
          <label>Notes</label>
          <textarea
            value={profile.notes}
            placeholder="Preferences, context, or things to remember…"
            onChange={(e) => setProfile((p) => ({ ...p, notes: e.target.value }))}
          />
        </div>
      </section>

      <p className="status-line">{message}</p>
      <div className="actions">
        <button className="btn primary" type="button" disabled={busy} onClick={save}>
          Save profile
        </button>
      </div>
    </div>
  );
}
