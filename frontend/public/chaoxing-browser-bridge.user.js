// ==UserScript==
// @name         Soulddog Learning Browser Bridge
// @namespace    https://soulddog.local/
// @version      0.1.0
// @description  登录后自动同步课程列表，接收平台指令打开课程页，并自动拉取 runner 脚本执行
// @match        *://*.chaoxing.com/*
// @match        *://v8.chaoxing.com/*
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @run-at       document-idle
// ==/UserScript==

(function () {
  "use strict";

  const DEFAULT_API_BASE = "http://127.0.0.1:8000";
  const STORAGE_KEYS = {
    apiBase: "soulddog_bridge_api_base",
    bridgeToken: "soulddog_bridge_token",
    lastCommandId: "soulddog_bridge_last_command_id",
  };
  const HEARTBEAT_MS = 5000;
  const COMMAND_POLL_MS = 4000;
  const COURSE_SYNC_MS = 8000;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const getValue = async (key, fallback = "") => {
    try {
      const value = await GM_getValue(key, fallback);
      return typeof value === "string" ? value : fallback;
    } catch {
      return fallback;
    }
  };

  const setValue = async (key, value) => {
    try {
      await GM_setValue(key, value);
    } catch (error) {
      console.warn("[bridge] save failed", key, error);
    }
  };

  const normalizeApiBase = (raw) => String(raw || DEFAULT_API_BASE).replace(/\/+$/, "");

  const getConfig = async () => {
    const apiBase = normalizeApiBase(await getValue(STORAGE_KEYS.apiBase, DEFAULT_API_BASE));
    const bridgeToken = String(await getValue(STORAGE_KEYS.bridgeToken, "")).trim();
    const lastCommandId = String(await getValue(STORAGE_KEYS.lastCommandId, "")).trim();
    return { apiBase, bridgeToken, lastCommandId };
  };

  const promptConfig = async () => {
    const current = await getConfig();
    const apiBase = window.prompt("Soulddog API Base", current.apiBase || DEFAULT_API_BASE);
    if (!apiBase) return;
    const bridgeToken = window.prompt("Bridge Token", current.bridgeToken || "");
    if (!bridgeToken) return;
    await setValue(STORAGE_KEYS.apiBase, normalizeApiBase(apiBase));
    await setValue(STORAGE_KEYS.bridgeToken, bridgeToken.trim());
    window.alert("Bridge 配置已保存，刷新页面后生效。");
  };

  const fetchJson = async (url, options = {}) => {
    const res = await fetch(url, {
      credentials: "include",
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data?.success === false) {
      throw new Error(data?.detail || data?.error || `HTTP ${res.status}`);
    }
    return data;
  };

  const looksLikeCourseHome = () => /mycourse/i.test(location.href) || document.querySelector(".course, .Mcon1, .course-list");
  const looksLikeCourseStudy = () => /studentstudy/i.test(location.href);

  const collectCourses = () => {
    const anchors = Array.from(document.querySelectorAll("a[href*='courseid'], a[href*='studentstudy'], a[href*='mycourse/stu']"));
    const seen = new Map();
    for (const anchor of anchors) {
      const url = anchor.href || anchor.getAttribute("href") || "";
      const title = (anchor.textContent || anchor.getAttribute("title") || "").replace(/\s+/g, " ").trim();
      if (!url || !title) continue;
      const card = anchor.closest("li, .course, .course-item, .Mcon1, .courseCover");
      const teacher = card?.querySelector(".teacher, .color3, .course-teacher")?.textContent?.replace(/\s+/g, " ").trim() || "";
      const image = card?.querySelector("img")?.getAttribute("src") || "";
      const courseId = /courseid=([^&]+)/i.exec(url)?.[1] || "";
      const classId = /clazzid=([^&]+)/i.exec(url)?.[1] || /classid=([^&]+)/i.exec(url)?.[1] || "";
      const key = `${title}::${url}`;
      if (seen.has(key)) continue;
      seen.set(key, { title, url, teacher, image, course_id: courseId, class_id: classId });
    }
    return Array.from(seen.values());
  };

  const sendHeartbeat = async (config) => {
    await fetchJson(`${config.apiBase}/api/chaoxing/browser-bridge/heartbeat`, {
      method: "POST",
      body: JSON.stringify({
        bridge_token: config.bridgeToken,
        current_url: location.href,
        page_title: document.title,
      }),
    });
  };

  const syncCourses = async (config) => {
    const courses = collectCourses();
    if (!courses.length) return;
    await fetchJson(`${config.apiBase}/api/chaoxing/browser-bridge/course-sync`, {
      method: "POST",
      body: JSON.stringify({
        bridge_token: config.bridgeToken,
        current_url: location.href,
        page_title: document.title,
        courses,
      }),
    });
    console.log("[bridge] synced courses", courses.length);
  };

  const ackCommand = async (config, commandId) => {
    await fetchJson(`${config.apiBase}/api/chaoxing/browser-bridge/ack`, {
      method: "POST",
      body: JSON.stringify({
        bridge_token: config.bridgeToken,
        command_id: commandId,
      }),
    });
    await setValue(STORAGE_KEYS.lastCommandId, commandId);
  };

  const runRemoteRunner = async (config, taskId) => {
    const data = await fetchJson(
      `${config.apiBase}/api/chaoxing/browser-bridge/runner-script?bridge_token=${encodeURIComponent(config.bridgeToken)}&task_id=${taskId}`
    );
    const script = String(data?.script || "").trim();
    if (!script) throw new Error("runner script 为空");
    window.eval(script);
    console.log("[bridge] runner executed for task", taskId);
  };

  const handleCommand = async (config, command) => {
    if (!command?.id || !command?.kind) return;
    if (command.kind !== "open_course") return;
    const url = String(command.course_url || "").trim();
    const taskId = Number(command.task_id || 0);
    if (!url || !taskId) return;

    await ackCommand(config, command.id);

    if (location.href !== url) {
      sessionStorage.setItem("soulddog_pending_runner_task_id", String(taskId));
      location.href = url;
      return;
    }

    await sleep(1200);
    await runRemoteRunner(config, taskId);
  };

  const pollCommands = async (config) => {
    const data = await fetchJson(`${config.apiBase}/api/chaoxing/browser-bridge/poll?bridge_token=${encodeURIComponent(config.bridgeToken)}`);
    const bridge = data?.bridge || {};
    const command = bridge.pending_command;
    const lastCommandId = String(await getValue(STORAGE_KEYS.lastCommandId, ""));
    if (command?.id && command.id !== lastCommandId) {
      console.log("[bridge] received command", command);
      await handleCommand(config, command);
    }
  };

  const tryResumePendingRunner = async (config) => {
    const taskId = Number(sessionStorage.getItem("soulddog_pending_runner_task_id") || "0");
    if (!taskId) return;
    if (!looksLikeCourseStudy() && !/courseid=/i.test(location.href)) return;
    sessionStorage.removeItem("soulddog_pending_runner_task_id");
    await sleep(1500);
    await runRemoteRunner(config, taskId);
  };

  const boot = async () => {
    const config = await getConfig();
    if (!config.bridgeToken) {
      console.warn("[bridge] missing bridge token");
      return;
    }

    try {
      await sendHeartbeat(config);
    } catch (error) {
      console.warn("[bridge] first heartbeat failed", error);
    }

    try {
      await tryResumePendingRunner(config);
    } catch (error) {
      console.warn("[bridge] resume runner failed", error);
    }

    window.setInterval(() => {
      sendHeartbeat(config).catch((error) => console.warn("[bridge] heartbeat failed", error));
    }, HEARTBEAT_MS);

    window.setInterval(() => {
      pollCommands(config).catch((error) => console.warn("[bridge] poll failed", error));
    }, COMMAND_POLL_MS);

    if (looksLikeCourseHome()) {
      syncCourses(config).catch((error) => console.warn("[bridge] initial course sync failed", error));
      window.setInterval(() => {
        syncCourses(config).catch((error) => console.warn("[bridge] course sync failed", error));
      }, COURSE_SYNC_MS);
    }

    console.log("[bridge] active", { href: location.href });
  };

  GM_registerMenuCommand("Configure Soulddog Bridge", () => {
    promptConfig().catch((error) => console.warn("[bridge] config failed", error));
  });

  boot().catch((error) => console.error("[bridge] boot failed", error));
})();
