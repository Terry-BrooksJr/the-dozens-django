/**
 * The Dozens - Modern JavaScript Module
 * Mobile-First Interactive Features
 * @module TheDozens
 */

'use strict';

// =============================================================================
// Configuration & Constants
// =============================================================================

const CONFIG = {
  highlightProjectId: document.body.dataset.highlightProjectId || '5g5kvvlg',
  environment: document.body.dataset.environment || 'production',
  version: 'commit:abcdefg12345',
  svgNamespace: 'http://www.w3.org/2000/svg',
  verticalSpacing: 50,
  animationDuration: 30000,
  preloaderDelay: 3000,
  phrases: [
    'Generating witty dialog',
    'Prepping Insults',
    'Offending Mothers',
    'Debating Fathers',
    'Irritating Aunts',
    'Annoying Grandmothers',
    'Disparaging Grandfathers',
    'Frustrating Matriarchs',
    'Cracking jokes',
    'Slacking off',
  ],
};

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Utility module for common helper functions
 */
const Utils = {
  /**
   * Shuffles an array using Fisher-Yates algorithm
   * @param {Array} array - Array to shuffle
   * @returns {Array} Shuffled array
   */
  shuffleArray(array) {
    const shuffled = [...array];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
  },

  /**
   * Checks if device is mobile based on touch support
   * @returns {boolean}
   */
  isMobileDevice() {
    return (
      'ontouchstart' in window ||
      navigator.maxTouchPoints > 0 ||
      window.matchMedia('(max-width: 768px)').matches
    );
  },

  /**
   * Checks if device supports hover interactions
   * @returns {boolean}
   */
  supportsHover() {
    return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  },

  /**
   * Debounce function for performance optimization
   * @param {Function} func - Function to debounce
   * @param {number} wait - Wait time in milliseconds
   * @returns {Function}
   */
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  /**
   * Throttle function for performance optimization
   * @param {Function} func - Function to throttle
   * @param {number} limit - Time limit in milliseconds
   * @returns {Function}
   */
  throttle(func, limit) {
    let inThrottle;
    return function executedFunction(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  },
};

// =============================================================================
// SVG Factory
// =============================================================================

/**
 * Factory for creating SVG elements
 */
class SVGFactory {
  /**
   * Creates an SVG element with specified properties
   * @param {string} tag - SVG tag name
   * @param {Object} properties - Element attributes
   * @param {Array} children - Child elements
   * @returns {SVGElement}
   */
  static create(tag, properties = {}, children = []) {
    const element = document.createElementNS(CONFIG.svgNamespace, tag);
    Object.entries(properties).forEach(([prop, value]) =>
      element.setAttribute(prop, value)
    );
    children.forEach((child) => element.appendChild(child));
    return element;
  }

  /**
   * Creates SVG checkmark icon
   * @param {number} index - Index for unique ID
   * @returns {SVGElement}
   */
  static createCheck(index) {
    const check = this.create('polygon', {
      points: '21.661,7.643 13.396,19.328 9.429,15.361 7.075,17.714 13.745,24.384 24.345,9.708',
      fill: 'rgba(255,255,255,1)',
      id: `loadingCheckSVG-${index}`,
    });

    const circleOutline = this.create('path', {
      d: 'M16,0C7.163,0,0,7.163,0,16s7.163,16,16,16s16-7.163,16-16S24.837,0,16,0z M16,30C8.28,30,2,23.72,2,16C2,8.28,8.28,2,16,2 c7.72,0,14,6.28,14,14C30,23.72,23.72,30,16,30z',
      fill: 'white',
    });

    const circle = this.create('circle', {
      id: `loadingCheckCircleSVG-${index}`,
      fill: 'rgba(255,255,255,0)',
      cx: '16',
      cy: '16',
      r: '15',
    });

    return this.create('g', {}, [circleOutline, circle, check]);
  }
}

// =============================================================================
// Preloader Animation
// =============================================================================

/**
 * Manages the preloader animation sequence
 */
class PreloaderAnimation {
  constructor() {
    this.config = {
      animationDuration: 3000,
      messageInterval: 1000,
      fadeOutDuration: 500,
      verticalSpacing: CONFIG.verticalSpacing,
    };

    this.phrases = Utils.shuffleArray([...CONFIG.phrases]);
    this.state = {
      isAnimating: false,
      startTime: null,
      currentPhraseIndex: 0,
    };

    this.elements = {
      preloader: document.getElementById('preloader'),
      phrasesContainer: document.getElementById('phrases'),
      messageElement: document.getElementById('loading-message'),
      contentWrapper: document.querySelector('.content-wrapper'),
    };

    this.messageInterval = null;
  }

  /**
   * Validates that all required DOM elements exist
   * @returns {boolean}
   */
  validateElements() {
    const missingElements = Object.entries(this.elements)
      .filter(([, element]) => !element)
      .map(([key]) => key);

    if (missingElements.length > 0) {
      console.error('[PreloaderAnimation] Missing required elements:', missingElements);
      return false;
    }
    return true;
  }

  /**
   * Sets up phrase elements in the DOM
   */
  setupPhrases() {
    this.elements.phrasesContainer.innerHTML = '';

    this.phrases.forEach((phrase, index) => {
      const div = document.createElement('div');
      div.className = 'phrase-item';
      div.style.transform = `translateY(${index * this.config.verticalSpacing}px)`;

      const span = document.createElement('span');
      span.className = 'phrase-text';
      span.textContent = `${phrase}...`;

      const checkSVG = SVGFactory.createCheck(index);

      div.appendChild(span);
      div.appendChild(checkSVG);
      this.elements.phrasesContainer.appendChild(div);
    });
  }

  /**
   * Updates animation frame
   * @param {number} progress - Animation progress (0-1)
   */
  updateAnimation(progress) {
    const translateY = -progress * (this.phrases.length * this.config.verticalSpacing);
    this.elements.phrasesContainer.style.transform = `translateY(${translateY}px)`;

    document.querySelectorAll('.phrase-item').forEach((item, index) => {
      const itemProgress = progress * this.phrases.length - index;
      if (itemProgress > 0) {
        item.classList.add('completed');
      }
    });
  }

  /**
   * Animation loop using requestAnimationFrame
   */
  animate() {
    if (!this.state.isAnimating) return;

    const elapsed = Date.now() - this.state.startTime;
    const progress = Math.min(elapsed / this.config.animationDuration, 1);

    if (progress < 1) {
      this.updateAnimation(progress);
      requestAnimationFrame(() => this.animate());
    } else {
      this.stop();
    }
  }

  /**
   * Updates the loading message text
   */
  updateMessage() {
    this.state.currentPhraseIndex = (this.state.currentPhraseIndex + 1) % this.phrases.length;
    this.elements.messageElement.textContent = `${this.phrases[this.state.currentPhraseIndex]}...`;
  }

  /**
   * Initializes and starts the preloader
   */
  initialize() {
    if (!this.validateElements()) return;
    this.setupPhrases();
    this.start();
  }

  /**
   * Starts the animation
   */
  start() {
    this.state.isAnimating = true;
    this.state.startTime = Date.now();
    this.messageInterval = setInterval(() => this.updateMessage(), this.config.messageInterval);
    this.animate();
  }

  /**
   * Stops the animation and shows main content
   */
  stop() {
    this.state.isAnimating = false;
    if (this.messageInterval) {
      clearInterval(this.messageInterval);
    }

    this.elements.preloader.classList.add('fade-out');
    setTimeout(() => {
      this.elements.preloader.style.display = 'none';
      this.elements.contentWrapper.classList.add('show');
      document.body.style.overflow = 'visible';
    }, this.config.fadeOutDuration);
  }
}

// =============================================================================
// Speech Bubble Controller
// =============================================================================

/**
 * Manages interactive speech bubble with joke display
 */
class SpeechBubbleController {
  constructor(apiUrl) {
    this.apiUrl = apiUrl;
    this.iconElement = document.getElementById('jod-icon');
    this.bubbleElement = null;
    this.speechContentElement = null;
    this.jokeContentElement = document.getElementById('joke-content');

    this.state = {
      isHovering: false,
      currentJoke: null,
      isLoading: false,
      isMobile: Utils.isMobileDevice(),
      supportsHover: Utils.supportsHover(),
    };

    this.init();
  }

  /**
   * Initializes the speech bubble controller
   */
  init() {
    if (!this.iconElement) {
      console.error('[SpeechBubbleController] jod-icon element not found');
      return;
    }

    this.createSpeechBubble();
    this.setupEventListeners();
    this.loadInitialJoke();
    this.setupResponsiveListeners();
  }

  /**
   * Creates the speech bubble DOM element
   */
  createSpeechBubble() {
    this.bubbleElement = document.createElement('div');
    this.bubbleElement.className = 'speech-bubble';
    this.bubbleElement.id = 'speech-bubble';

    this.speechContentElement = document.createElement('span');
    this.speechContentElement.id = 'speech-bubble-content';
    this.speechContentElement.textContent = 'Loading joke...';

    this.bubbleElement.appendChild(this.speechContentElement);
    document.body.appendChild(this.bubbleElement);
  }

  /**
   * Sets up event listeners based on device capabilities
   */
  setupEventListeners() {
    // Click event - works on all devices
    this.iconElement.addEventListener('click', (e) => {
      e.preventDefault();
      this.handleClick();
    });

    // Touch events for mobile
    if (this.state.isMobile) {
      this.iconElement.addEventListener('touchstart', (e) => {
        e.preventDefault();
        this.handleClick();
      }, { passive: false });
    }

    // Mouse events for desktop with hover support
    if (this.state.supportsHover) {
      this.iconElement.addEventListener('mouseenter', (e) => this.handleMouseEnter(e));
      this.iconElement.addEventListener('mouseleave', () => this.handleMouseLeave());
      this.iconElement.addEventListener('mousemove', Utils.throttle((e) => this.positionBubble(e), 16));
    }
  }

  /**
   * Sets up responsive listeners for viewport changes
   */
  setupResponsiveListeners() {
    const mobileQuery = window.matchMedia('(max-width: 768px)');
    const hoverQuery = window.matchMedia('(hover: hover) and (pointer: fine)');

    mobileQuery.addEventListener('change', (e) => {
      this.state.isMobile = e.matches;
    });

    hoverQuery.addEventListener('change', (e) => {
      this.state.supportsHover = e.matches;
    });
  }

  /**
   * Handles mouse enter event
   * @param {MouseEvent} e - Mouse event
   */
  async handleMouseEnter(e) {
    if (this.state.isMobile) return;

    this.state.isHovering = true;
    this.positionBubble(e);
    this.showBubble();

    if (this.state.currentJoke) {
      this.speechContentElement.textContent = this.state.currentJoke;
    } else if (!this.state.isLoading) {
      await this.loadNewJoke();
    }
  }

  /**
   * Handles mouse leave event
   */
  handleMouseLeave() {
    if (this.state.isMobile) return;
    this.state.isHovering = false;
    this.hideBubble();
  }

  /**
   * Handles click/tap event
   */
  async handleClick() {
    if (!this.state.isLoading) {
      // Show bubble on mobile when clicked
      if (this.state.isMobile) {
        this.showBubble();
        // Auto-hide after 5 seconds on mobile
        setTimeout(() => this.hideBubble(), 5000);
      }
      await this.loadNewJoke();
    }
  }

  /**
   * Shows the speech bubble
   */
  showBubble() {
    this.bubbleElement.classList.add('show');
  }

  /**
   * Hides the speech bubble
   */
  hideBubble() {
    this.bubbleElement.classList.remove('show');
  }

  /**
   * Positions the speech bubble relative to the icon
   * @param {MouseEvent} e - Mouse event
   */
  positionBubble(e) {
    if (this.state.isMobile) {
      // Center on mobile
      const iconRect = this.iconElement.getBoundingClientRect();
      this.bubbleElement.style.left = '50%';
      this.bubbleElement.style.transform = 'translateX(-50%)';
      this.bubbleElement.style.top = `${iconRect.bottom + 15}px`;
      return;
    }

    const iconRect = this.iconElement.getBoundingClientRect();
    const viewport = {
      width: window.innerWidth,
      height: window.innerHeight,
    };

    const bubbleWidth = this.bubbleElement.offsetWidth || 250;
    const bubbleHeight = this.bubbleElement.offsetHeight || 80;

    let left = iconRect.left + iconRect.width / 2 - bubbleWidth / 2;
    let top = iconRect.top - bubbleHeight - 15;

    // Adjust horizontal position
    if (left < 10) {
      left = 10;
      this.bubbleElement.classList.add('tail-left');
      this.bubbleElement.classList.remove('tail-right');
    } else if (left + bubbleWidth > viewport.width - 10) {
      left = viewport.width - bubbleWidth - 10;
      this.bubbleElement.classList.add('tail-right');
      this.bubbleElement.classList.remove('tail-left');
    } else {
      this.bubbleElement.classList.remove('tail-left', 'tail-right');
    }

    // Adjust vertical position
    if (top < 10) {
      top = iconRect.bottom + 15;
    }

    this.bubbleElement.style.left = `${left}px`;
    this.bubbleElement.style.top = `${top}px`;
  }

  /**
   * Loads a new joke from the API
   */
  async loadNewJoke() {
    if (this.state.isLoading) return;

    this.state.isLoading = true;
    this.bubbleElement.classList.add('loading');

    if (this.speechContentElement) {
      this.speechContentElement.textContent = 'Loading new joke...';
    }

    try {
      const response = await fetch(this.apiUrl);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      this.state.currentJoke = data.content || Object.values(data)[0];

      if (this.speechContentElement) {
        this.speechContentElement.textContent = this.state.currentJoke;
      }

      if (this.jokeContentElement) {
        this.jokeContentElement.textContent = this.state.currentJoke;
      }
    } catch (error) {
      console.error('[SpeechBubbleController] Error loading joke:', error);
      const errorMessage = 'Failed to load joke. Please try again.';

      if (this.speechContentElement) {
        this.speechContentElement.textContent = errorMessage;
      }

      if (this.jokeContentElement) {
        this.jokeContentElement.textContent = errorMessage;
      }

      this.state.currentJoke = null;
    } finally {
      this.state.isLoading = false;
      this.bubbleElement.classList.remove('loading');
    }
  }

  /**
   * Loads the initial joke on page load
   */
  async loadInitialJoke() {
    try {
      const response = await fetch(this.apiUrl);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      this.state.currentJoke = data.content || Object.values(data)[0];

      if (this.speechContentElement) {
        this.speechContentElement.textContent = this.state.currentJoke;
      }

      if (this.jokeContentElement) {
        this.jokeContentElement.textContent = this.state.currentJoke;
      }
    } catch (error) {
      console.error('[SpeechBubbleController] Error loading initial joke:', error);
      const fallbackJoke = 'Yo momma is so fat that when she walked past the TV, I missed three episodes.';
      this.state.currentJoke = fallbackJoke;

      if (this.speechContentElement) {
        this.speechContentElement.textContent = fallbackJoke;
      }
    }
  }
}

// =============================================================================
// UI Controller
// =============================================================================

/**
 * Manages general UI interactions
 */
class UIController {
  /**
   * Sets up UI event listeners
   */
  static setupEventListeners() {
    // Only add hover animations on devices that support it
    if (Utils.supportsHover()) {
      this.setupHoverAnimations();
    }

    // Setup mobile-friendly interactions
    this.setupMobileInteractions();
  }

  /**
   * Sets up hover animations for desktop
   */
  static setupHoverAnimations() {
    const animatableElements = document.querySelectorAll('.nav-bttn, h1');

    animatableElements.forEach((element) => {
      element.addEventListener('mouseenter', () => {
        element.classList.add('animate__animated', 'animate__pulse');
      });

      element.addEventListener('mouseleave', () => {
        element.classList.remove('animate__animated', 'animate__pulse');
      });
    });

    // Icon animations
    const icon = document.getElementById('jod-icon');
    if (icon) {
      icon.addEventListener('mouseenter', () => {
        icon.classList.add('animate__animated', 'animate__heartbeat');
      });

      icon.addEventListener('mouseleave', () => {
        icon.classList.remove('animate__animated', 'animate__heartbeat');
      });
    }
  }

  /**
   * Sets up mobile-specific interactions
   */
  static setupMobileInteractions() {
    if (Utils.isMobileDevice()) {
      // Prevent double-tap zoom on buttons
      const buttons = document.querySelectorAll('button, .btn');
      buttons.forEach((button) => {
        button.addEventListener('touchend', (e) => {
          e.preventDefault();
          button.click();
        }, { passive: false });
      });
    }
  }
}

// =============================================================================
// Monitoring Auto-Switcher
// =============================================================================

/**
 * Manages the monitoring/observability card content switching
 */
class MonitoringSwitcher {
  constructor() {
    this.state = 'prom';
    this.interval = null;
    this.switchDuration = 30000; // 30 seconds

    this.elements = {
      cardTitle: document.getElementById('monitoring-card-title'),
      cardText: document.getElementById('monitoring-card-text'),
      cardImg: document.getElementById('monitoring-img'),
      cardLink: document.getElementById('monitoring-card-link'),
      cardDesc: document.getElementById('monitoring-card-desc'),
      cardTooltip: document.getElementById('monitoring-tooltip'),
    };
  }

  /**
   * Renders the monitoring card content based on state
   * @param {string} state - Either 'prom' or 'highlight'
   */
  render(state) {
    if (!this.elements.cardTitle) return;

    const content = {
      highlight: {
        title: 'Observability',
        text: 'Highlight.io',
        img: 'https://nyc3.digitaloceanspaces.com/yo-momma/static/assets/highlight_logo.png',
        linkText: 'More on Highlight.io',
        linkHref: 'https://highlight.io/',
        desc: 'Prometheus and Highlight.io work together to keep The Dozens API reliable and transparent. Highlight.io captures logs, traces, and front-end events for end-to-end visibility.',
      },
      prom: {
        title: 'Monitoring',
        text: 'Prometheus',
        img: 'https://nyc3.digitaloceanspaces.com/yo-momma/static/assets/prom_logo.png',
        linkText: 'More on Prometheus',
        linkHref: 'https://prometheus.io/',
        desc: 'Prometheus and Highlight.io work together to keep The Dozens API reliable and transparent. Prometheus collects metrics (latency, request counts, cache hits, error rates) so performance can be tracked and tuned.',
      },
    };

    const data = content[state];

    this.elements.cardTitle.textContent = data.title;
    this.elements.cardText.textContent = data.text;
    this.elements.cardImg.src = data.img;
    this.elements.cardLink.textContent = data.linkText;
    this.elements.cardLink.href = data.linkHref;
    this.elements.cardDesc.textContent = data.desc;

    if (this.elements.cardTooltip) {
      this.elements.cardTooltip.setAttribute('title', data.desc);
    }
  }

  /**
   * Switches between monitoring states
   */
  switch() {
    this.state = this.state === 'prom' ? 'highlight' : 'prom';
    this.render(this.state);
  }

  /**
   * Starts the auto-switching interval
   */
  start() {
    if (this.interval) return;
    this.switch();
    this.interval = setInterval(() => this.switch(), this.switchDuration);
  }

  /**
   * Stops the auto-switching interval
   */
  stop() {
    if (!this.interval) return;
    clearInterval(this.interval);
    this.interval = null;
  }
}

// =============================================================================
// Initialization
// =============================================================================

/**
 * Initialize application when DOM is ready
 */
function initializeApp() {
  console.log('[TheDozens] Initializing application...');

  // Initialize Highlight.io monitoring
  if (typeof H !== 'undefined' && CONFIG.highlightProjectId) {
    H.init(CONFIG.highlightProjectId, {
      environment: CONFIG.environment,
      version: CONFIG.version,
      networkRecording: {
        enabled: true,
        recordHeadersAndBody: true,
        urlBlocklist: [],
      },
    });
    console.log('[TheDozens] Highlight.io initialized');
  }

  // Register GSAP plugins if available
  if (typeof gsap !== 'undefined' && gsap.registerPlugin) {
    gsap.registerPlugin(TextPlugin);
  }

  // Initialize preloader
  const preloader = new PreloaderAnimation();
  preloader.initialize();

  // Get API URL from Django template or use default
  const apiUrl = document.body.dataset.apiUrl || window.location.origin + '/api/insult/random';

  // Initialize speech bubble controller
  const speechBubble = new SpeechBubbleController(apiUrl);

  // Initialize UI controller
  UIController.setupEventListeners();

  // Initialize monitoring switcher
  const monitoringSwitcher = new MonitoringSwitcher();

  // Setup tab switching for monitoring
  const tabSelector = 'a[data-bs-toggle="pill"], a[data-toggle="pill"]';
  document.addEventListener('shown.bs.tab', (e) => {
    if (e.target?.id === 'monitoring-tab') {
      monitoringSwitcher.start();
    } else if (e.relatedTarget?.id === 'monitoring-tab') {
      monitoringSwitcher.stop();
    }
  });

  document.addEventListener('hidden.bs.tab', (e) => {
    if (e.target?.id === 'monitoring-tab') {
      monitoringSwitcher.stop();
    }
  });

  // Auto-stop preloader after delay
  setTimeout(() => {
    preloader.stop();
  }, CONFIG.preloaderDelay);

  console.log('[TheDozens] Application initialized successfully');
}

// =============================================================================
// Event Listeners
// =============================================================================

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeApp);
} else {
  initializeApp();
}

// Handle window resize with debouncing
window.addEventListener(
  'resize',
  Utils.debounce(() => {
    console.log('[TheDozens] Window resized');
    // Re-check device capabilities
    const isMobile = Utils.isMobileDevice();
    document.body.classList.toggle('is-mobile', isMobile);
  }, 250)
);

// Export for potential module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    Utils,
    SVGFactory,
    PreloaderAnimation,
    SpeechBubbleController,
    UIController,
    MonitoringSwitcher,
  };
}
