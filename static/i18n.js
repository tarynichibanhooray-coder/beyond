(function (global) {
  "use strict";

  var STRINGS = {
    en: {
      pageTitle: "Before — demo",
      title: "In This Time Before",
      timeRemaining: "Time remaining",
      tokenUsage: "Token usage",
      tokIn: "in",
      tokOut: "out",
      tokUsed: "used",
      tokRem: "rem",
      councilIntro: "The council",
      councilSpeaking: "Council speaking",
      startSession: "Start session",
      idle: "Idle",
      response: "Response",
      responsePlaceholder: "Type your response…",
      finalQuestion: "Your final question",
      downloadConversation: "Download conversation",
      council: "Council",
      councilSpeaks: "The council speaks…",
      speakerSpeaks: "{name} speaks…",
      speakerThinks: "{name} thinks…",
      speakerSpeaksShort: "{name} speaks",
      formulatingQuestion: "Formulating your next question…",
      asksNext: "{name} asks next",
      question: "Question",
      conversation: "Conversation",
      observations: "Observations",
      done: "Done",
      starting: "Starting…",
      errorServer: "Error (server not running?)",
      errorCheckServer: "Error (check server)",
      errorDownload: "Could not download session",
      error: "Error",
      responseTo: "Response to: {question}",
      mock: "mock",
      tokensDepleted: "The tokens are depleted. Please return tomorrow.",
    },
    es: {
      pageTitle: "Before — demo",
      title: "En este tiempo previo",
      timeRemaining: "Tiempo restante",
      tokenUsage: "Uso de tokens",
      tokIn: "entr",
      tokOut: "sal",
      tokUsed: "usado",
      tokRem: "rest",
      councilIntro: "El consejo",
      councilSpeaking: "El consejo habla",
      startSession: "Iniciar sesión",
      idle: "Inactivo",
      response: "Respuesta",
      responsePlaceholder: "Escribe tu respuesta…",
      finalQuestion: "Tu pregunta final",
      downloadConversation: "Descargar conversación",
      council: "Consejo",
      councilSpeaks: "El consejo habla…",
      speakerSpeaks: "{name} habla…",
      speakerThinks: "{name} piensa…",
      speakerSpeaksShort: "{name} habla",
      formulatingQuestion: "Formulando tu próxima pregunta…",
      asksNext: "{name} pregunta a continuación",
      question: "Pregunta",
      conversation: "Conversación",
      observations: "Observaciones",
      done: "Listo",
      starting: "Iniciando…",
      errorServer: "Error (¿servidor no iniciado?)",
      errorCheckServer: "Error (revisa el servidor)",
      errorDownload: "No se pudo descargar la sesión",
      error: "Error",
      responseTo: "Respuesta a: {question}",
      mock: "simulado",
      tokensDepleted: "Los tokens se han agotado. Vuelve mañana.",
    },
  };

  var COUNCIL_I18N = {
    es: {
      arabi: {
        role: "El Umbral",
        bio_role:
          "Lee lo que ya se abre en esta persona—no esperando a que la vida comience, " +
          "sino encontrándola en el lugar intermedio donde ocurren las cosas más reales.",
        bio_pro:
          "Filósofo místico andalusí cuya obra sobre la imaginación, el umbral " +
          "y el yo como espejo sigue siendo una de las metafísicas más rigurosas " +
          "de la experiencia humana.",
      },
      morrison: {
        role: "El Claro",
        bio_role:
          "Ve a través del lenguaje lo que realmente está presente: la palabra elegida " +
          "frente a otra, lo que se nombra y lo que se deja cuidadosamente sin nombrar. " +
          "Sostiene las historias que te formaron y lo que debe nombrarse antes de poder vivirse. " +
          "Práctica y sin ilusiones: ni cósmica ni urgente, pero clara.",
        bio_pro:
          "Escritora y profesora estadounidense cuya ficción y crítica insisten " +
          "en que lo no dicho y lo no presenciado sigue moldeando el presente.",
      },
      kierkegaard: {
        role: "El Salto",
        bio_role:
          "Nombra el pavor de la libertad—la elección que pospones—y te empuja " +
          "hacia una pregunta que exige decidir cómo vivir.",
        bio_pro:
          "Filósofo y teólogo danés, fundador del pensamiento existencial, " +
          "que escribió sobre la fe, la angustia y el salto de la elección.",
      },
    },
  };

  function resolveLocale() {
    var langs = [global.navigator.language].concat(global.navigator.languages || []);
    for (var i = 0; i < langs.length; i += 1) {
      var tag = String(langs[i] || "").toLowerCase();
      if (tag.indexOf("es") === 0) return "es";
      if (tag.indexOf("en") === 0) return "en";
    }
    return "en";
  }

  var locale = resolveLocale();

  function interpolate(text, vars) {
    if (!vars) return text;
    return text.replace(/\{(\w+)\}/g, function (_m, key) {
      return vars[key] != null ? String(vars[key]) : "";
    });
  }

  function t(key, vars) {
    var bucket = STRINGS[locale] || STRINGS.en;
    var fallback = STRINGS.en[key] || key;
    return interpolate(bucket[key] != null ? bucket[key] : fallback, vars);
  }

  function applyStaticUi() {
    global.document.documentElement.lang = locale;
    global.document.title = t("pageTitle");
    global.document.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    global.document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      el.placeholder = t(el.getAttribute("data-i18n-placeholder"));
    });
    global.document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
    });
  }

  function localizeCouncilMembers(members) {
    if (locale !== "es" || !members) return members;
    var patch = COUNCIL_I18N.es;
    return members.map(function (m) {
      var tr = patch[m.id];
      return tr ? Object.assign({}, m, tr) : m;
    });
  }

  function apiHeaders(extra) {
    var headers = { "Accept-Language": locale === "es" ? "es" : "en" };
    if (extra) {
      Object.keys(extra).forEach(function (k) {
        headers[k] = extra[k];
      });
    }
    return headers;
  }

  function formatNumber(n) {
    if (n == null) return "∞";
    return Number(n).toLocaleString(locale === "es" ? "es" : "en-US");
  }

  global.BeforeI18n = {
    locale: locale,
    t: t,
    applyStaticUi: applyStaticUi,
    localizeCouncilMembers: localizeCouncilMembers,
    apiHeaders: apiHeaders,
    formatNumber: formatNumber,
  };
})(window);
