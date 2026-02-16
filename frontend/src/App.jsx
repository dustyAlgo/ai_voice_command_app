import { useEffect, useMemo, useState } from "react";

import { fetchShoppingList, login, register, sendVoiceCommand, setAuthToken } from "./api";

function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegisterMode, setIsRegisterMode] = useState(false);

  const [token, setToken] = useState(localStorage.getItem("access_token") || "");
  const [listItems, setListItems] = useState([]);
  const [transcript, setTranscript] = useState("");
  const [language, setLanguage] = useState("en-IN");
  const [voiceResponse, setVoiceResponse] = useState(null);

  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isSubmittingVoice, setIsSubmittingVoice] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState("");

  const recognition = useMemo(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      return null;
    }
    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = false;
    return rec;
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }

    setAuthToken(token);
    localStorage.setItem("access_token", token);
    refreshList();
  }, [token]);

  async function refreshList() {
    try {
      setIsLoadingList(true);
      setError("");
      const response = await fetchShoppingList();
      setListItems(response.data || []);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to fetch shopping list.");
    } finally {
      setIsLoadingList(false);
    }
  }

  async function handleAuth(event) {
    event.preventDefault();
    setError("");

    try {
      if (isRegisterMode) {
        await register(email, password);
      }
      const response = await login(email, password);
      setToken(response.data.access);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.response?.data?.error || "Authentication failed.");
    }
  }

  function logout() {
    localStorage.removeItem("access_token");
    setAuthToken("");
    setToken("");
    setListItems([]);
    setVoiceResponse(null);
    setTranscript("");
  }

  function startListening() {
    if (!recognition) {
      setError("Web Speech API is not supported in this browser.");
      return;
    }

    recognition.lang = language;
    recognition.onstart = () => {
      setError("");
      setIsListening(true);
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => {
      setIsListening(false);
      setError("Voice recognition failed. Try again.");
    };
    recognition.onresult = (event) => {
      const text = event.results?.[0]?.[0]?.transcript || "";
      setTranscript(text);
    };
    recognition.start();
  }

  async function submitVoiceCommand(event) {
    event?.preventDefault();
    if (!transcript.trim()) {
      return;
    }

    try {
      setIsSubmittingVoice(true);
      setError("");
      const response = await sendVoiceCommand(transcript.trim());
      setVoiceResponse(response.data);
      setListItems(response.data.updated_list || []);
    } catch (err) {
      setError(err?.response?.data?.error || "Voice command failed.");
    } finally {
      setIsSubmittingVoice(false);
    }
  }

  if (!token) {
    return (
      <div className="app">
        <h1>Voice Shopping Assistant</h1>
        <div className="card">
          <form onSubmit={handleAuth}>
            <div className="row">
              <input className="full" placeholder="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              <input className="full" placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <div className="row" style={{ marginTop: 10 }}>
              <button type="submit">{isRegisterMode ? "Register + Login" : "Login"}</button>
              <button type="button" onClick={() => setIsRegisterMode((prev) => !prev)}>
                {isRegisterMode ? "Use Login" : "Create Account"}
              </button>
            </div>
          </form>
          {error && <p className="small">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1>Voice Shopping Assistant</h1>
        <button onClick={logout}>Logout</button>
      </div>

      <div className="card">
        <form onSubmit={submitVoiceCommand}>
          <div className="row">
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="en-IN">Auto (English + Hindi)</option>
              <option value="en-US">English</option>
              <option value="hi-IN">Hindi</option>
            </select>
            <button type="button" onClick={startListening} disabled={isListening || isSubmittingVoice}>
              {isListening ? "Listening..." : "Start Voice"}
            </button>
          </div>

          <textarea
            className="full"
            rows={3}
            placeholder='Example: "Add 2 almond milk and remove bread"'
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            style={{ marginTop: 10 }}
          />

          <div className="row" style={{ marginTop: 10 }}>
            <button type="submit" disabled={isSubmittingVoice || !transcript.trim()}>
              {isSubmittingVoice ? "Processing..." : "Send Command"}
            </button>
          </div>
        </form>
      </div>

      <div className="card">
        <h3>Shopping List</h3>
        {isLoadingList ? (
          <p className="small">Loading list...</p>
        ) : listItems.length === 0 ? (
          <p className="small">No items yet.</p>
        ) : (
          <div className="row" style={{ flexDirection: "column" }}>
            {listItems.map((item) => (
              <div className="item-grid" key={item.id}>
                <strong>{item.product_name}</strong>
                <span className="badge">Qty: {item.quantity}</span>
                <span className="small">{item.category}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {voiceResponse && (
        <div className="card">
          <h3>Assistant Response</h3>
          <p>{voiceResponse.message}</p>
          <p className="small">Status: {voiceResponse.status}</p>
          <p className="small">Detected language: {voiceResponse.detected_language}</p>

          <h4>Suggestions</h4>
          {(voiceResponse.suggestions || []).length === 0 ? (
            <p className="small">No suggestions.</p>
          ) : (
            (voiceResponse.suggestions || []).map((s, idx) => (
              <p className="small" key={idx}>
                {s.item}: {s.reason}
              </p>
            ))
          )}

          <h4>Substitutes</h4>
          {(voiceResponse.substitutes || []).length === 0 ? (
            <p className="small">No substitutes.</p>
          ) : (
            (voiceResponse.substitutes || []).map((s, idx) => (
              <p className="small" key={idx}>
                {s.original} -> {s.alternative} ({s.reason})
              </p>
            ))
          )}

          <h4>Search Results</h4>
          {(voiceResponse.search_results || []).length === 0 ? (
            <p className="small">No matches.</p>
          ) : (
            (voiceResponse.search_results || []).map((result, idx) => (
              <p className="small" key={idx}>
                {result.name} | {result.brand || "No brand"} | ${result.price} | {result.category}
              </p>
            ))
          )}
        </div>
      )}

      {error && (
        <div className="card">
          <p className="small">{error}</p>
        </div>
      )}
    </div>
  );
}

export default App;
