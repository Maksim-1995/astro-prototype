(() => {
  'use strict';

  const body = document.body;
  const story = document.querySelector('[data-story]');
  const stickyScene = story?.querySelector('.story__sticky');
  const viewportProbe = document.querySelector('[data-viewport-probe]');
  const dialog = document.querySelector('#beta-dialog');
  const progressLabel = document.querySelector('[data-progress-label]');
  const chapters = story ? [...story.querySelectorAll('[data-chapter]')] : [];
  const privacyChapter = story?.querySelector('[data-chapter="privacy"]');
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
  const smoothstep = (start, end, value) => {
    const position = clamp((value - start) / (end - start));
    return position * position * (3 - 2 * position);
  };
  const stableViewportHeight = () => viewportProbe?.getBoundingClientRect().height
    || window.innerHeight;
  const usesStaticFlow = () => motionPreference.matches || stableViewportHeight() < 700;
  let scheduledFrame = 0;
  let pointerX = 0;
  let pointerY = 0;

  function updateScene() {
    scheduledFrame = 0;
    if (!story) return;

    const staticFlow = usesStaticFlow();
    story.classList.toggle('is-static-flow', staticFlow);
    const rect = story.getBoundingClientRect();
    const stickyHeight = stickyScene?.getBoundingClientRect().height || window.innerHeight;
    const scrollDistance = Math.max(story.offsetHeight - stickyHeight, 1);
    const progress = clamp(-rect.top / scrollDistance);
    const sceneProgress = clamp((progress - 0.2) / 0.65);
    const approach = smoothstep(0.10, 0.55, progress);
    const departure = smoothstep(0.22, 0.60, progress);
    const privacyEnter = smoothstep(0.50, 0.82, progress);
    const portalProgress = smoothstep(0.24, 0.80, progress);
    const portalVisibility = smoothstep(0.22, 0.45, progress)
      * (1 - smoothstep(0.74, 0.95, progress));

    const privacyInView = privacyChapter
      && privacyChapter.getBoundingClientRect().top <= stableViewportHeight() * 0.5;
    const currentScene = staticFlow
      ? (privacyInView ? 'privacy' : 'intro')
      : (progress >= 0.58 ? 'privacy' : 'intro');
    story.dataset.scene = currentScene;
    story.style.setProperty('--progress', staticFlow ? '0' : progress.toFixed(4));
    story.style.setProperty('--scene-progress', staticFlow ? '0' : sceneProgress.toFixed(4));
    story.style.setProperty('--approach', staticFlow ? '0' : approach.toFixed(4));
    story.style.setProperty('--departure', staticFlow ? '0' : departure.toFixed(4));
    story.style.setProperty('--privacy-enter', staticFlow ? '0' : privacyEnter.toFixed(4));
    story.style.setProperty('--portal-progress', staticFlow ? '0' : portalProgress.toFixed(4));
    story.style.setProperty('--portal-visibility', staticFlow ? '0' : portalVisibility.toFixed(4));
    story.style.setProperty('--hero-opacity', staticFlow ? '1' : (1 - 0.82 * departure).toFixed(4));
    story.style.setProperty('--intro-opacity', staticFlow ? '1' : (1 - departure).toFixed(4));
    story.style.setProperty('--pointer-x', staticFlow ? '0' : pointerX.toFixed(4));
    story.style.setProperty('--pointer-y', staticFlow ? '0' : pointerY.toFixed(4));

    // Both scenes remain available in the normal document flow when motion is
    // reduced or the viewport is short. Off-stage scenes do not receive focus.
    const activeChapter = chapters.find((chapter) => chapter.dataset.chapter === currentScene);
    chapters.forEach((chapter) => {
      if (staticFlow || chapter === activeChapter) {
        chapter.removeAttribute('inert');
        if (staticFlow) chapter.removeAttribute('aria-hidden');
        else chapter.setAttribute('aria-hidden', 'false');
      }
    });
    chapters.forEach((chapter) => {
      if (staticFlow || chapter === activeChapter) return;
      if (!dialog?.open && chapter.contains(document.activeElement) && activeChapter) {
        if (!activeChapter.hasAttribute('tabindex')) activeChapter.tabIndex = -1;
        activeChapter.focus({ preventScroll: true });
      }
      chapter.setAttribute('inert', '');
      chapter.setAttribute('aria-hidden', 'true');
    });

    if (progressLabel) {
      const label = currentScene === 'intro' ? '01 / 02' : '02 / 02';
      if (progressLabel.textContent !== label) progressLabel.textContent = label;
    }
  }

  function scheduleSceneUpdate() {
    if (!scheduledFrame) scheduledFrame = window.requestAnimationFrame(updateScene);
  }

  window.addEventListener('scroll', scheduleSceneUpdate, { passive: true });
  window.addEventListener('resize', scheduleSceneUpdate, { passive: true });

  if (story) {
    story.addEventListener('pointermove', (event) => {
      if (event.pointerType !== 'mouse' || motionPreference.matches) return;
      pointerX = clamp((event.clientX / window.innerWidth) * 2 - 1, -1, 1);
      pointerY = clamp((event.clientY / window.innerHeight) * 2 - 1, -1, 1);
      scheduleSceneUpdate();
    }, { passive: true });

    story.addEventListener('pointerleave', () => {
      pointerX = 0;
      pointerY = 0;
      scheduleSceneUpdate();
    }, { passive: true });

    if ('ResizeObserver' in window) {
      new ResizeObserver(scheduleSceneUpdate).observe(story);
    }
  }

  const handleMotionChange = () => {
    pointerX = 0;
    pointerY = 0;
    scheduleSceneUpdate();
  };

  if (motionPreference.addEventListener) {
    motionPreference.addEventListener('change', handleMotionChange);
  } else if (motionPreference.addListener) {
    motionPreference.addListener(handleMotionChange);
  }

  updateScene();

  const scrollToPosition = (top) => window.scrollTo({
    top,
    behavior: motionPreference.matches ? 'auto' : 'smooth',
  });

  document.querySelectorAll('[data-scroll-next]').forEach((control) => {
    control.addEventListener('click', (event) => {
      event.preventDefault();
      closeMenu();
      if (!story) return;
      if (control.hasAttribute('data-scroll-continue') && story.dataset.scene === 'privacy') {
        const afterword = document.querySelector('.afterword');
        if (afterword) {
          afterword.scrollIntoView({
            behavior: motionPreference.matches ? 'auto' : 'smooth',
            block: 'start',
          });
          return;
        }
      }
      if (usesStaticFlow() && privacyChapter) {
        privacyChapter.scrollIntoView({
          behavior: motionPreference.matches ? 'auto' : 'smooth',
          block: 'start',
        });
        return;
      }
      const storyTop = window.scrollY + story.getBoundingClientRect().top;
      const stickyHeight = stickyScene?.getBoundingClientRect().height || window.innerHeight;
      const scrollDistance = Math.max(story.offsetHeight - stickyHeight, 0);
      scrollToPosition(storyTop + scrollDistance * 0.9);
    });
  });

  document.querySelectorAll('[data-scroll-top]').forEach((control) => {
    control.addEventListener('click', (event) => {
      event.preventDefault();
      scrollToPosition(0);
    });
  });

  const signals = [...document.querySelectorAll('[data-signal]')];
  const cueTitle = document.querySelector('[data-cue-title]');
  const cueBody = document.querySelector('[data-cue-body]');
  const defaultCue = {
    title: 'Притяжение начинается с тебя.',
    body: 'Нажми на светящийся сигнал — у каждой встречи своя история.',
  };

  function selectSignal(selectedSignal) {
    if (story) story.dataset.signalActive = String(Boolean(selectedSignal));
    signals.forEach((signal) => {
      const active = signal === selectedSignal;
      signal.setAttribute('aria-pressed', String(active));
      signal.dataset.active = String(active);
    });
    if (cueTitle) cueTitle.textContent = selectedSignal?.dataset.title || defaultCue.title;
    if (cueBody) cueBody.textContent = selectedSignal?.dataset.body || defaultCue.body;
  }

  signals.forEach((signal) => {
    signal.addEventListener('click', () => {
      selectSignal(signal.getAttribute('aria-pressed') === 'true' ? null : signal);
    });

    // Native buttons already support Enter and Space. Keep any non-button
    // scene objects operable if the visual markup uses a different element.
    if (signal.tagName !== 'BUTTON') {
      signal.setAttribute('role', 'button');
      signal.tabIndex = 0;
      signal.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        signal.click();
      });
    }
  });
  selectSignal(null);

  const navToggle = document.querySelector('[data-nav-toggle]');
  function closeMenu() {
    body.classList.remove('is-menu-open');
    navToggle?.setAttribute('aria-expanded', 'false');
  }

  navToggle?.addEventListener('click', () => {
    const open = navToggle.getAttribute('aria-expanded') !== 'true';
    navToggle.setAttribute('aria-expanded', String(open));
    body.classList.toggle('is-menu-open', open);
  });

  document.querySelectorAll('nav a, nav button').forEach((link) => {
    link.addEventListener('click', closeMenu);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && body.classList.contains('is-menu-open')) {
      closeMenu();
      navToggle?.focus({ preventScroll: true });
    }
  });

  let dialogTrigger = null;

  function closeDialog() {
    if (!dialog) return;
    if (typeof dialog.close === 'function') {
      dialog.close();
    } else {
      dialog.removeAttribute('open');
      dialogTrigger?.focus({ preventScroll: true });
    }
  }

  document.querySelectorAll('[data-demo-open]').forEach((control) => {
    control.addEventListener('click', (event) => {
      event.preventDefault();
      closeMenu();
      if (!dialog || dialog.open) return;
      dialogTrigger = control;
      if (typeof dialog.showModal === 'function') {
        dialog.showModal();
      } else {
        dialog.setAttribute('open', '');
        dialog.querySelector('[data-demo-close]')?.focus({ preventScroll: true });
      }
    });
  });

  document.querySelectorAll('[data-demo-close]').forEach((control) => {
    control.addEventListener('click', closeDialog);
  });

  dialog?.addEventListener('close', () => {
    dialogTrigger?.focus({ preventScroll: true });
  });

  dialog?.addEventListener('click', (event) => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    const outside = event.clientX < rect.left || event.clientX > rect.right
      || event.clientY < rect.top || event.clientY > rect.bottom;
    if (outside) closeDialog();
  });

  const message = document.querySelector('[data-message]');
  const deleteMessage = document.querySelector('[data-message-delete]');
  const messageStatus = document.querySelector('[data-message-status]');
  const initialMessageStatus = messageStatus?.textContent || '';
  const initialDeleteLabel = deleteMessage?.textContent || 'Удалить сообщение';
  let messageDeleted = false;
  let disappearanceTimer = 0;

  deleteMessage?.addEventListener('click', () => {
    if (!message) return;
    window.clearTimeout(disappearanceTimer);
    messageDeleted = !messageDeleted;

    if (!messageDeleted) {
      message.hidden = false;
      message.classList.remove('is-vanishing');
      if (messageStatus) messageStatus.textContent = initialMessageStatus;
      deleteMessage.textContent = initialDeleteLabel;
      deleteMessage.setAttribute('aria-pressed', 'false');
      return;
    }

    message.classList.add('is-vanishing');
    deleteMessage.textContent = 'Повторить демонстрацию';
    deleteMessage.setAttribute('aria-pressed', 'true');
    if (messageStatus) messageStatus.textContent = 'Сообщение исчезает…';

    const finishDisappearance = () => {
      message.hidden = true;
      if (messageStatus) {
        messageStatus.textContent = 'Сообщение исчезло. Так выглядит приватность.';
      }
    };

    if (motionPreference.matches) {
      finishDisappearance();
    } else {
      disappearanceTimer = window.setTimeout(finishDisappearance, 450);
    }
  });

  const revealElements = [...document.querySelectorAll('[data-reveal]')];
  if (!('IntersectionObserver' in window) || motionPreference.matches) {
    revealElements.forEach((element) => element.classList.add('is-visible'));
  } else {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -24px 0px' });
    revealElements.forEach((element) => revealObserver.observe(element));
  }
})();
