import { useEffect } from "react";

export default function SetUidGuard() {
  useEffect(() => {
    const hash = window.location.hash || "";
    const queryIndex = hash.indexOf("?");
    if (queryIndex !== -1) {
      const query = hash.slice(queryIndex + 1);
      const params = new URLSearchParams(query);
      const uid = params.get("user_id");

      if (uid) {
        localStorage.setItem("user_id", uid);
        console.log("✅ 自動補上 user_id：", uid);

        // ✅ 同步傳給後端，綁定 session
        fetch("/set_uid", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ uid }),
          credentials: "include"
        }).then(() => {
          console.log("✅ user_id 已送出給後端");
        }).catch(err => {
          console.error("❌ 傳送 user_id 給後端失敗", err);
        });
      }
    }
  }, []);

  return null;
}
