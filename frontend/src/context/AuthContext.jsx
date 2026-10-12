import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { setLogoutHandler, tokenStore } from "../api/client.js";

const AuthContext = createContext(null);
const USER_KEY = "studyrag.user";

function loadUser() {
  try {
    return tokenStore.get() ? JSON.parse(sessionStorage.getItem(USER_KEY)) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(loadUser);
  const navigate = useNavigate();

  const logout = useCallback(() => {
    tokenStore.clear();
    sessionStorage.removeItem(USER_KEY);
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  useEffect(() => {
    setLogoutHandler(logout);
  }, [logout]);

  const saveSession = (data) => {
    tokenStore.set({ access_token: data.access_token, refresh_token: data.refresh_token });
    sessionStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const login = async (email, password) => saveSession((await api.post("/auth/login", { email, password })).data);
  const register = async (name, email, password) =>
    saveSession((await api.post("/auth/register", { name, email, password })).data);

  return <AuthContext.Provider value={{ user, login, register, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
