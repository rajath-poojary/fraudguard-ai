import { useEffect } from "react";
import { useRouter } from "next/router";

export default function Home() {
  const router = useRouter();
  useEffect(() => { void router.replace(localStorage.getItem("fraudguard_token") ? "/dashboard" : "/login"); }, [router]);
  return <div className="boot-screen">Opening workspace...</div>;
}
