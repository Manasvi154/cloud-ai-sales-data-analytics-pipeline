document.addEventListener("DOMContentLoaded", () => {
  const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
  const sidebarOverlay = document.querySelector("[data-sidebar-overlay]");
  const sidebarLinks = document.querySelectorAll("[data-sidebar] a, [data-sidebar] button");

  const closeSidebar = () => {
    document.body.classList.remove("sidebar-open");
    if (sidebarToggle) {
      sidebarToggle.setAttribute("aria-expanded", "false");
    }
  };

  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
      const willOpen = !document.body.classList.contains("sidebar-open");
      document.body.classList.toggle("sidebar-open", willOpen);
      sidebarToggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener("click", closeSidebar);
  }

  sidebarLinks.forEach((node) => {
    node.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 900px)").matches) {
        closeSidebar();
      }
    });
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSidebar();
    }
  });

  const revealNodes = Array.from(document.querySelectorAll(".reveal"));
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            obs.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.1 }
    );

    revealNodes.forEach((node, idx) => {
      node.style.transitionDelay = `${Math.min(idx * 60, 360)}ms`;
      observer.observe(node);
    });
  } else {
    revealNodes.forEach((node) => node.classList.add("visible"));
  }

  document.querySelectorAll(".progress-fill[data-progress]").forEach((node) => {
    const progress = Number(node.dataset.progress || "0");
    const safeValue = Math.max(0, Math.min(progress, 100));
    window.setTimeout(() => {
      node.style.width = `${safeValue}%`;
    }, 180);
  });

  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const targetId = button.dataset.targetId;
    const targetInput = targetId ? document.getElementById(targetId) : null;
    if (!targetInput) {
      return;
    }

    const openIcon = button.querySelector(".password-icon-open");
    const closedIcon = button.querySelector(".password-icon-closed");

    const syncPasswordToggleState = () => {
      const showingPassword = targetInput.type === "text";
      button.setAttribute("aria-label", showingPassword ? "Hide password" : "Show password");
      button.setAttribute("aria-pressed", showingPassword ? "true" : "false");
      openIcon?.classList.toggle("hidden", showingPassword);
      closedIcon?.classList.toggle("hidden", !showingPassword);
    };

    button.addEventListener("click", () => {
      targetInput.type = targetInput.type === "password" ? "text" : "password";
      syncPasswordToggleState();
    });

    syncPasswordToggleState();
  });

  const jobMonitorNode = document.getElementById("job-monitor");
  if (jobMonitorNode) {
    const statusUrl = jobMonitorNode.dataset.statusUrl || "";
    const pollSeconds = Number(jobMonitorNode.dataset.pollSeconds || "3");
    const stageNode = document.querySelector("[data-job-stage]");
    const statusNode = document.querySelector("[data-job-status]");
    const progressNode = document.querySelector("[data-job-progress]");
    const timelineNode = document.querySelector(".timeline");

    const progressFromStatus = (status) => {
      const normalized = String(status || "").toUpperCase();
      if (normalized === "UPLOADED") return 25;
      if (normalized === "ORCHESTRATION_STARTED") return 45;
      if (normalized === "RUNNING") return 65;
      if (normalized === "SUCCEEDED" || normalized === "FAILED") return 100;
      return 55;
    };

    const badgeHtml = (status) => {
      const normalized = String(status || "UNKNOWN").toUpperCase();
      if (normalized === "SUCCEEDED") {
        return `<span class="status-badge success">${normalized}</span>`;
      }
      if (normalized === "FAILED") {
        return `<span class="status-badge failed">${normalized}</span>`;
      }
      return `<span class="status-badge running">${normalized}</span>`;
    };

    const renderEvents = (events) => {
      if (!timelineNode || !Array.isArray(events)) {
        return;
      }

      timelineNode.innerHTML = "";
      const recentEvents = events.slice(-6);
      if (!recentEvents.length) {
        const fallbackEventNode = document.createElement("p");
        fallbackEventNode.className = "timeline-item";
        fallbackEventNode.textContent = "Waiting for pipeline events...";
        timelineNode.appendChild(fallbackEventNode);
        return;
      }

      recentEvents.forEach((event) => {
        const lineNode = document.createElement("p");
        lineNode.className = "timeline-item";
        const eventTs = event.event_ts || "";
        const stage = event.stage || "UNKNOWN_STAGE";
        const message = event.message || "Pipeline event received.";
        lineNode.textContent = `${eventTs} | ${stage} | ${message}`;
        timelineNode.appendChild(lineNode);
      });
    };

    const applyJobStatus = (payload) => {
      const job = payload?.job || {};
      const status = String(job.status || "UNKNOWN").toUpperCase();
      const stage = job.stage || "IN_PROGRESS";

      if (statusNode) {
        statusNode.innerHTML = badgeHtml(status);
      }
      if (stageNode) {
        stageNode.textContent = `Current stage: ${stage}`;
      }
      if (progressNode) {
        const progress = progressFromStatus(status);
        progressNode.dataset.progress = String(progress);
        progressNode.style.width = `${progress}%`;
      }
      renderEvents(payload?.events || []);
    };

    let pollTimerId = null;

    const pollStatus = async () => {
      if (!statusUrl) {
        return;
      }
      try {
        const response = await fetch(statusUrl, { credentials: "same-origin" });
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        applyJobStatus(payload);

        const normalizedStatus = String(payload?.job?.status || "").toUpperCase();
        if (payload?.is_terminal && normalizedStatus === "SUCCEEDED" && payload?.results_url) {
          if (pollTimerId) {
            window.clearInterval(pollTimerId);
          }
          window.location.assign(payload.results_url);
        }
      } catch (error) {
        // Keep retrying; transient failures are expected during refresh.
      }
    };

    const intervalMs = Math.max(1, pollSeconds) * 1000;
    pollTimerId = window.setInterval(pollStatus, intervalMs);
    pollStatus();
  }
});
