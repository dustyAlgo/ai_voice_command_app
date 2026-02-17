import { useEffect, useMemo, useState } from "react";

import {
  fetchShoppingList,
  login,
  register,
  removeShoppingItem,
  searchCatalog,
  sendVoiceCommand,
  setAuthToken,
  updateShoppingItemQuantity,
} from "./api";

function toFilterChips(appliedSearchFilters) {
  if (!appliedSearchFilters || typeof appliedSearchFilters !== "object") {
    return [];
  }

  const chips = [];
  if (appliedSearchFilters.name) {
    chips.push(`Item: ${appliedSearchFilters.name}`);
  }
  if (appliedSearchFilters.brand) {
    chips.push(`Brand: ${appliedSearchFilters.brand}`);
  }
  if (appliedSearchFilters.size) {
    chips.push(`Size: ${appliedSearchFilters.size}`);
  }
  if (appliedSearchFilters.min_price != null) {
    chips.push(`Min: $${appliedSearchFilters.min_price}`);
  }
  if (appliedSearchFilters.max_price != null) {
    chips.push(`Max: $${appliedSearchFilters.max_price}`);
  }
  return chips;
}

const EMPTY_CATALOG_SEARCH = {
  name: "",
  brand: "",
  size: "",
  minPrice: "",
  maxPrice: "",
};

function hasAnyCatalogInput(searchState) {
  return Boolean(
    searchState.name.trim() ||
      searchState.brand.trim() ||
      searchState.size.trim() ||
      String(searchState.minPrice).trim() ||
      String(searchState.maxPrice).trim()
  );
}

function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegisterMode, setIsRegisterMode] = useState(false);

  const [token, setToken] = useState(localStorage.getItem("access_token") || "");
  const [listItems, setListItems] = useState([]);
  const [transcript, setTranscript] = useState("");
  const [language, setLanguage] = useState("en-IN");
  const [voiceResponse, setVoiceResponse] = useState(null);
  const [catalogSearch, setCatalogSearch] = useState(EMPTY_CATALOG_SEARCH);
  const [catalogResults, setCatalogResults] = useState(null);
  const [catalogAppliedFilters, setCatalogAppliedFilters] = useState({});

  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isSubmittingVoice, setIsSubmittingVoice] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isCatalogSearching, setIsCatalogSearching] = useState(false);
  const [isCatalogVoiceListening, setIsCatalogVoiceListening] = useState(false);
  const [itemActionId, setItemActionId] = useState(null);
  const [isAuthSubmitting, setIsAuthSubmitting] = useState(false);
  const [error, setError] = useState("");
  const commandSearchFilterChips = toFilterChips(voiceResponse?.applied_search_filters);
  const catalogSearchFilterChips = toFilterChips(catalogAppliedFilters);

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

  useEffect(() => {
    if (!hasAnyCatalogInput(catalogSearch) && catalogResults !== null && !isCatalogSearching) {
      setCatalogResults(null);
      setCatalogAppliedFilters({});
    }
  }, [catalogSearch, catalogResults, isCatalogSearching]);

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
    if (isAuthSubmitting) {
      return;
    }
    setError("");

    try {
      setIsAuthSubmitting(true);
      if (isRegisterMode) {
        await register(email, password);
      }
      const response = await login(email, password);
      setToken(response.data.access);
    } catch (err) {
      if (err?.code === "ECONNABORTED") {
        setError("Request timed out. Please try again.");
      } else {
        setError(err?.response?.data?.detail || err?.response?.data?.error || "Authentication failed.");
      }
    } finally {
      setIsAuthSubmitting(false);
    }
  }

  function logout() {
    localStorage.removeItem("access_token");
    setAuthToken("");
    setToken("");
    setListItems([]);
    setVoiceResponse(null);
    setTranscript("");
    setCatalogSearch(EMPTY_CATALOG_SEARCH);
    setCatalogResults(null);
    setCatalogAppliedFilters({});
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

  function startCatalogVoiceSearch() {
    if (!recognition) {
      setError("Web Speech API is not supported in this browser.");
      return;
    }

    recognition.lang = language;
    recognition.onstart = () => {
      setError("");
      setIsCatalogVoiceListening(true);
    };
    recognition.onend = () => setIsCatalogVoiceListening(false);
    recognition.onerror = () => {
      setIsCatalogVoiceListening(false);
      setError("Voice recognition failed. Try again.");
    };
    recognition.onresult = (event) => {
      const spokenText = event.results?.[0]?.[0]?.transcript || "";
      setCatalogSearch((prev) => ({ ...prev, name: spokenText }));
      runCatalogSearch({ transcript: spokenText });
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

  function applyCatalogFiltersToFields(filters) {
    setCatalogSearch({
      name: filters?.name || "",
      brand: filters?.brand || "",
      size: filters?.size || "",
      minPrice: filters?.min_price != null ? String(filters.min_price) : "",
      maxPrice: filters?.max_price != null ? String(filters.max_price) : "",
    });
  }

  function buildCatalogFormPayload() {
    return {
      name: catalogSearch.name.trim() || null,
      brand: catalogSearch.brand.trim() || null,
      size: catalogSearch.size.trim() || null,
      min_price: String(catalogSearch.minPrice).trim() || null,
      max_price: String(catalogSearch.maxPrice).trim() || null,
    };
  }

  async function runCatalogSearch(payload) {
    try {
      setIsCatalogSearching(true);
      setError("");
      const response = await searchCatalog(payload);
      const results = response.data?.search_results || [];
      const appliedFilters = response.data?.applied_search_filters || {};
      setCatalogResults(results);
      setCatalogAppliedFilters(appliedFilters);
      applyCatalogFiltersToFields(appliedFilters);
    } catch (err) {
      setError(err?.response?.data?.error || "Catalog search failed.");
      setCatalogResults([]);
      setCatalogAppliedFilters({});
    } finally {
      setIsCatalogSearching(false);
    }
  }

  async function submitCatalogSearch(event) {
    event.preventDefault();
    await runCatalogSearch(buildCatalogFormPayload());
  }

  function clearCatalogSearch() {
    setCatalogSearch(EMPTY_CATALOG_SEARCH);
    setCatalogResults(null);
    setCatalogAppliedFilters({});
  }

  async function changeItemQuantity(itemId, delta) {
    if (!itemId || !delta) {
      return;
    }

    try {
      setItemActionId(itemId);
      setError("");
      const response = await updateShoppingItemQuantity(itemId, delta);
      const updatedItem = response.data;
      setListItems((prev) =>
        prev.map((item) => (item.id === itemId ? { ...item, quantity: updatedItem.quantity } : item))
      );
    } catch (err) {
      setError(err?.response?.data?.error || "Failed to update quantity.");
    } finally {
      setItemActionId(null);
    }
  }

  async function removeItemFromCart(itemId) {
    if (!itemId) {
      return;
    }
    try {
      setItemActionId(itemId);
      setError("");
      await removeShoppingItem(itemId);
      setListItems((prev) => prev.filter((item) => item.id !== itemId));
    } catch (err) {
      setError(err?.response?.data?.error || "Failed to remove item.");
    } finally {
      setItemActionId(null);
    }
  }

  if (!token) {
    return (
      <div className="app">
        <h1>Voice Shopping Assistant</h1>
        <div className="card">
          <form onSubmit={handleAuth}>
            <div className="row">
              <input
                className="full"
                placeholder="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isAuthSubmitting}
              />
              <input
                className="full"
                placeholder="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isAuthSubmitting}
              />
            </div>
            <div className="row" style={{ marginTop: 10 }}>
              <button type="submit" disabled={isAuthSubmitting}>
                {isAuthSubmitting ? (
                  <span className="button-loading-content">
                    <span className="button-spinner" />
                    {isRegisterMode ? "Registering..." : "Logging in..."}
                  </span>
                ) : (
                  (isRegisterMode ? "Register + Login" : "Login")
                )}
              </button>
              <button type="button" onClick={() => setIsRegisterMode((prev) => !prev)} disabled={isAuthSubmitting}>
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
              {isListening ? "Listening..." : "Command AI"}
            </button>
          </div>

          <textarea
            className="full"
            rows={3}
            placeholder='Example: Add 2 almond milk and remove bread'
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
        <h3>Shopping Cart</h3>
        <div className="search-section">
          <form onSubmit={submitCatalogSearch}>
            <div className="row search-primary-row">
              <input
                className="search-box"
                placeholder="Search item (e.g. organic apples)"
                value={catalogSearch.name}
                onChange={(e) => setCatalogSearch((prev) => ({ ...prev, name: e.target.value }))}
              />
              <button type="button" onClick={startCatalogVoiceSearch} disabled={isCatalogVoiceListening || isCatalogSearching}>
                {isCatalogVoiceListening ? "Listening..." : "Voice Search"}
              </button>
              <button type="submit" disabled={isCatalogSearching}>
                {isCatalogSearching ? "Searching..." : "Search"}
              </button>
              <button type="button" className="secondary-button" onClick={clearCatalogSearch} disabled={isCatalogSearching}>
                Clear
              </button>
            </div>
            <div className="row search-filter-row">
              <input
                placeholder="Brand"
                value={catalogSearch.brand}
                onChange={(e) => setCatalogSearch((prev) => ({ ...prev, brand: e.target.value }))}
              />
              <input
                placeholder="Size (e.g. 100g, 1L)"
                value={catalogSearch.size}
                onChange={(e) => setCatalogSearch((prev) => ({ ...prev, size: e.target.value }))}
              />
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="Min price"
                value={catalogSearch.minPrice}
                onChange={(e) => setCatalogSearch((prev) => ({ ...prev, minPrice: e.target.value }))}
              />
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="Max price"
                value={catalogSearch.maxPrice}
                onChange={(e) => setCatalogSearch((prev) => ({ ...prev, maxPrice: e.target.value }))}
              />
            </div>
          </form>

          {catalogSearchFilterChips.length > 0 && (
            <div className="chip-wrap">
              {catalogSearchFilterChips.map((chip) => (
                <span className="filter-chip" key={`catalog-${chip}`}>
                  {chip}
                </span>
              ))}
            </div>
          )}
        </div>

        {isCatalogSearching ? (
          <p className="small">Searching catalog...</p>
        ) : catalogResults !== null ? (
          catalogResults.length === 0 ? (
            <p className="small">No matches found</p>
          ) : (
            <div className="search-results-grid">
              {catalogResults.map((result, idx) => (
                <div className="search-result-card" key={`${result.name}-${idx}`}>
                  <p>
                    <strong>{result.name}</strong>
                  </p>
                  <p className="small">Brand: {result.brand || "No brand"}</p>
                  <p className="small">Category: {result.category}</p>
                  <p className="small">Size: {result.size || "N/A"}</p>
                  <p className="small">Price: ${result.price}</p>
                </div>
              ))}
            </div>
          )
        ) : isLoadingList ? (
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
                <div className="item-controls">
                  <button
                    type="button"
                    className="mini-btn"
                    onClick={() => changeItemQuantity(item.id, -1)}
                    disabled={itemActionId === item.id || item.quantity <= 1}
                  >
                    -
                  </button>
                  <button
                    type="button"
                    className="mini-btn"
                    onClick={() => changeItemQuantity(item.id, 1)}
                    disabled={itemActionId === item.id}
                  >
                    +
                  </button>
                  <button
                    type="button"
                    className="danger-btn"
                    onClick={() => removeItemFromCart(item.id)}
                    disabled={itemActionId === item.id}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {voiceResponse && (
        <div className="card">
          <h3>Assistant Response</h3>
          <p className="response-message">{voiceResponse.message}</p>
          <div className="meta-row">
            <span className="badge">Status: {voiceResponse.status}</span>
            <span className="badge">Language: {voiceResponse.detected_language}</span>
          </div>

          <h4>Parsed Search Filters</h4>
          {commandSearchFilterChips.length === 0 ? (
            <p className="small">No search filters detected in the command.</p>
          ) : (
            <div className="chip-wrap">
              {commandSearchFilterChips.map((chip) => (
                <span className="filter-chip" key={chip}>
                  {chip}
                </span>
              ))}
            </div>
          )}

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
                {s.original} {"->"} {s.alternative} ({s.reason})
              </p>
            ))
          )}

          <h4>Search Results</h4>
          {(voiceResponse.search_results || []).length === 0 ? (
            <p className="small">No matches.</p>
          ) : (
            <div className="search-results-grid">
              {(voiceResponse.search_results || []).map((result, idx) => (
                <div className="search-result-card" key={`${result.name}-${idx}`}>
                  <p>
                    <strong>{result.name}</strong>
                  </p>
                  <p className="small">Brand: {result.brand || "No brand"}</p>
                  <p className="small">Category: {result.category}</p>
                  <p className="small">Size: {result.size || "N/A"}</p>
                  <p className="small">Price: ${result.price}</p>
                </div>
              ))}
            </div>
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
