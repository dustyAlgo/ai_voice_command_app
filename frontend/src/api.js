import axios from "axios";

function normalizeApiBaseUrl(rawUrl) {
  const fallback = "http://127.0.0.1:8000/api";
  const candidate = (rawUrl || fallback).trim().replace(/\/+$/, "");
  if (!candidate) {
    return fallback;
  }
  if (candidate.endsWith("/api")) {
    return candidate;
  }
  return `${candidate}/api`;
}

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
});

export function setAuthToken(token) {
  if (!token) {
    delete api.defaults.headers.common.Authorization;
    return;
  }
  api.defaults.headers.common.Authorization = `Bearer ${token}`;
}

export async function register(email, password) {
  return api.post("/auth/register/", { email, password });
}

export async function login(email, password) {
  return api.post("/auth/login/", { email, password });
}

export async function fetchShoppingList() {
  return api.get("/shopping/list/");
}

export async function sendVoiceCommand(transcript) {
  return api.post("/voice/command/", { transcript });
}

export async function searchCatalog(payload) {
  return api.post("/shopping/search/", payload);
}

export async function updateShoppingItemQuantity(itemId, delta) {
  return api.post(`/shopping/item/${itemId}/quantity/`, { delta });
}

export async function removeShoppingItem(itemId) {
  return api.post(`/shopping/item/${itemId}/remove/`, {});
}

export default api;
