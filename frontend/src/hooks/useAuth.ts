import { useRouter } from "next/router";
import { useEffect, useState } from "react";

export function useAuth(required = true) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const storedToken = localStorage.getItem("fraudguard_token");
    setToken(storedToken);
    setReady(true);
    if (required && !storedToken) void router.replace("/login");
  }, [required, router]);

  const logout = () => {
    localStorage.removeItem("fraudguard_token");
    setToken(null);
    void router.replace("/login");
  };

  return { ready, token, logout };
}
