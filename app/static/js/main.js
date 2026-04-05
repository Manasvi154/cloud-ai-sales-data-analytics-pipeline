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
});
