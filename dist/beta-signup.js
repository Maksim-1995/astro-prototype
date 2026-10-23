(() => {
  'use strict';

  const form = document.querySelector('[data-beta-form]');
  if (!form) return;

  // Read public deployment configuration once. An incomplete configuration
  // deliberately keeps the form closed instead of sending personal data.
  const config = window.ASTRO_CONFIG || {};
  const dialog = form.closest('dialog');
  const email = form.querySelector('[name="email"]');
  const consent = form.querySelector('[name="consent"]');
  const website = form.querySelector('[name="website"]');
  const fields = [...form.querySelectorAll('[data-beta-field]')];
  const submit = form.querySelector('[data-beta-submit]');
  const submitLabel = form.querySelector('[data-beta-submit-label]');
  const status = form.querySelector('[data-beta-status]');
  const availability = dialog?.querySelector('[data-beta-availability]');
  const policyLink = form.querySelector('[data-beta-policy]');
  const policyFallback = form.querySelector('[data-beta-policy-fallback]');
  const success = dialog?.querySelector('[data-beta-success]');
  const successText = dialog?.querySelector('[data-beta-success-text]');
  const acceptedMessage = 'Заявка принята. Если вы ещё не в списке, мы добавим ваш email.';
  const errors = {
    email: form.querySelector('[data-beta-error="email"]'),
    consent: form.querySelector('[data-beta-error="consent"]'),
  };
  let pending = false;

  function getApiEndpoint(value) {
    if (typeof value !== 'string') return null;
    try {
      const base = value.trim();
      const url = base === ''
        ? new URL('/api/v1/beta-signups/', window.location.origin)
        : new URL(`${base.replace(/\/+$/, '')}/api/v1/beta-signups/`);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null;
      if (url.search || url.hash) return null;
      return url.href;
    } catch {
      return null;
    }
  }

  function getPolicyUrl(value) {
    if (typeof value !== 'string' || !value.trim()) return null;
    const candidate = value.trim();
    if (!/^https?:\/\//i.test(candidate) && !candidate.startsWith('/')) return null;
    try {
      const url = new URL(candidate, window.location.origin);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null;
      return url.href;
    } catch {
      return null;
    }
  }

  const endpoint = getApiEndpoint(config.apiBaseUrl);
  const policyUrl = getPolicyUrl(config.privacyPolicyUrl);
  const configured = Boolean(endpoint && policyUrl && email && consent && submit);

  if (policyLink && policyUrl) {
    policyLink.href = policyUrl;
    policyLink.hidden = false;
    if (policyFallback) policyFallback.hidden = true;
  }

  if (availability) availability.hidden = configured;
  fields.forEach((field) => { field.disabled = !configured; });
  if (submit) submit.disabled = !configured;

  function setStatus(message, state = '') {
    if (!status) return;
    status.textContent = message;
    status.dataset.state = state;
  }

  function clearErrors() {
    Object.values(errors).forEach((element) => {
      if (element) element.textContent = '';
    });
    email?.removeAttribute('aria-invalid');
    consent?.removeAttribute('aria-invalid');
    setStatus('');
  }

  function showFieldError(name, message) {
    const field = name === 'email' ? email : consent;
    if (field) field.setAttribute('aria-invalid', 'true');
    if (errors[name]) errors[name].textContent = message;
  }

  function setPending(value) {
    pending = value;
    form.setAttribute('aria-busy', String(value));
    fields.forEach((field) => { field.disabled = value || !configured; });
    if (submit) submit.disabled = value || !configured;
    if (submitLabel) submitLabel.textContent = value ? 'Отправляем…' : 'Отправить заявку';
  }

  function firstError(value) {
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.find((item) => typeof item === 'string') || '';
    return '';
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!configured || pending) return;

    clearErrors();
    let invalidField = null;
    if (!email.validity.valid) {
      showFieldError('email', email.validity.valueMissing ? 'Укажи email.' : 'Укажи корректный email.');
      invalidField = email;
    }
    if (!consent.checked) {
      showFieldError('consent', 'Подтверди согласие на обработку персональных данных.');
      invalidField ||= consent;
    }
    if (invalidField) {
      setStatus('Проверь выделенные поля.', 'error');
      invalidField.focus();
      return;
    }

    const payload = {
      email: email.value.trim(),
      consent: consent.checked,
      website: website?.value || '',
    };
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    let focusAfterRequest = null;
    setPending(true);
    setStatus('Отправляем заявку…');

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        credentials: 'omit',
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      let data = null;
      try {
        data = await response.json();
      } catch (error) {
        if (error.name === 'AbortError') throw error;
      }

      if (response.status === 202) {
        setStatus(acceptedMessage, 'success');
        if (successText) successText.textContent = firstError(data?.detail) || acceptedMessage;
        if (success) {
          form.hidden = true;
          success.hidden = false;
          if (dialog?.open) success.focus({ preventScroll: true });
        }
        form.reset();
        return;
      }

      if (response.status === 400) {
        let firstInvalid = null;
        ['email', 'consent'].forEach((name) => {
          const message = firstError(data?.[name]);
          if (!message) return;
          showFieldError(name, message);
          firstInvalid ||= name === 'email' ? email : consent;
        });
        setStatus(firstError(data?.detail) || 'Проверь выделенные поля и попробуй ещё раз.', 'error');
        focusAfterRequest = firstInvalid;
        return;
      }

      if (response.status === 429) {
        const retryAfter = Number(response.headers.get('Retry-After'));
        const wait = Number.isFinite(retryAfter) && retryAfter > 0
          ? ` Попробуй ещё раз через ${Math.ceil(retryAfter)} с.`
          : ' Попробуй ещё раз чуть позже.';
        setStatus(`Слишком много попыток.${wait}`, 'error');
        return;
      }

      setStatus('Сервис временно недоступен. Попробуй позже — email остался в форме.', 'error');
    } catch (error) {
      setStatus(error.name === 'AbortError'
        ? 'Сервер не ответил вовремя. Попробуй ещё раз — email остался в форме.'
        : 'Не удалось отправить заявку. Проверь соединение и попробуй ещё раз.', 'error');
    } finally {
      window.clearTimeout(timeout);
      setPending(false);
      if (dialog?.open) focusAfterRequest?.focus();
    }
  });
})();
