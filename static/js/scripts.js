// Get configuration from environment or data attributes
const HIGHLIGHT_PROJECT_ID =
  document.body.dataset.highlightProjectId || "5g5kvvlg";

// Highlight.io Monitoring Configuration
const HIGHLIGHT_CONFIG = {
  environment: document.body.dataset.environment || "production",
  version: "commit:abcdefg12345",
  networkRecording: {
    enabled: true,
    recordHeadersAndBody: true,
    urlBlocklist: [],
  },
};

// Constants
const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const VERTICAL_SPACING = 50;
const ANIMATION_DURATION = 30000;
const API_URL = "https://api.yo-momma.net/insult";
const PRELOADER_DELAY = 3000;
const PHRASES = [
  "Generating witty dialog",
  "Prepping Insults",
  "Offending Mothers",
  "Debating Fathers",
  "Irritating Aunts",
  "Annoying Grandmothers",
  "Disparaging Grandfathers",
  "Frustrating Matriarchs",
  "Cracking jokes",
  "Slacking off",
];

// Initialize Highlight.io
if (typeof H !== "undefined" && HIGHLIGHT_PROJECT_ID) {
  H.init(HIGHLIGHT_PROJECT_ID, HIGHLIGHT_CONFIG);
}

// SVG Creation Utilities
class SVGFactory {
  /**
   * Creates an SVG element with the specified tag, properties, and children.
   * This is a utility function for creating SVG elements.
   * @param {string} tag - The tag name of the SVG element to create.
   * @param {object} properties - An object containing the attributes to set on the element.
   * @param {array} children - An array of child elements to append to the created element.
   * @returns {Element} The newly created SVG element.
   */
  static create(tag, properties = {}, children = []) {
    const element = document.createElementNS(SVG_NAMESPACE, tag);
    Object.entries(properties).forEach(([prop, value]) =>
      element.setAttribute(prop, value)
    );
    children.forEach((child) => element.appendChild(child));
    return element;
  }

  /**
   * Creates an SVG text element for displaying a phrase.
   * This creates the text element with default styling and appends an ellipsis.
   * @param {string} phrase - The phrase to display.
   * @param {number} yOffset - The vertical offset for positioning the text.
   * @returns {Element} The newly created SVG text element.
   */
  static createPhrase(phrase, yOffset) {
    return this.create(
      "text",
      {
        fill: "white",
        x: "50",
        y: yOffset.toString(),
        "font-size": "18",
        "font-family": "Arial",
      },
      [document.createTextNode(phrase + "...")]
    );
  }
  /**
   * Creates an SVG checkmark icon.
   * This creates a checkmark within a circle, used for loading animations.
   * @param {number} yOffset - The vertical offset for positioning the checkmark.
   * @param {number} index - An index used to generate unique IDs for the SVG elements.
   * @returns {Element} The newly created SVG group element containing the checkmark.
   */
  static createCheck(yOffset, index) {
    const check = this.create("polygon", {
      points:
        "21.661,7.643 13.396,19.328 9.429,15.361 7.075,17.714 13.745,24.384 24.345,9.708",
      fill: "rgba(255,255,255,1)",
      id: `loadingCheckSVG-${index}`,
    });

    const circleOutline = this.create("path", {
      d: "M16,0C7.163,0,0,7.163,0,16s7.163,16,16,16s16-7.163,16-16S24.837,0,16,0z M16,30C8.28,30,2,23.72,2,16C2,8.28,8.28,2,16,2 c7.72,0,14,6.28,14,14C30,23.72,23.72,30,16,30z",
      fill: "white",
    });

    const circle = this.create("circle", {
      id: `loadingCheckCircleSVG-${index}`,
      fill: "rgba(255,255,255,0)",
      cx: "16",
      cy: "16",
      r: "15",
    });

    return this.create("g", {}, [circleOutline, circle, check]);
  }
}
/**
 * Controls the preloader animation.
 * This class manages the animation of phrases and checkmarks during the preloading phase.
 */
class PreloaderAnimation {
  constructor() {
    this.config = {
      animationDuration: 3000,
      messageInterval: 1000,
      fadeOutDuration: 500,
      verticalSpacing: 50,
    };

    this.phrases = PHRASES;
    this.state = {
      isAnimating: false,
      startTime: Date.now(),
      currentPhraseIndex: 0,
    };

    this.elements = {
      preloader: document.getElementById("preloader"),
      phrasesContainer: document.getElementById("phrases"),
      messageElement: document.getElementById("loading-message"),
      contentWrapper: document.querySelector(".content-wrapper"),
    };

    // Bind methods
    this.animate = this.animate.bind(this);
    this.updateMessage = this.updateMessage.bind(this);
  }
  /**
   * Shuffles the elements of an array randomly.
   * Uses the Fisher-Yates shuffle algorithm.
   * @param {array} array - The array to shuffle.
   * @returns {array} The shuffled array.
   */
  shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
  }
  /**
   * Initializes the preloader animation.
   * Confirms all UI Elements Are Valid, then sets up Phrases and Starts Animation
   *
   * @returns {void}
   */
  initialize() {
    if (!this.validateElements()) return;

    this.setupPhrases();
    this.start();
  }
  /**
   * Utility Function to Validate Required UI Elements
   * Checks if all required elements are present in the DOM.
   * Logs an error if any elements are missing.
   * @returns {boolean} Returns true if all required elements are present, false otherwise.
   */

  validateElements() {
    const missingElements = Object.entries(this.elements)
      .filter(([key, element]) => !element)
      .map(([key]) => key);

    if (missingElements.length > 0) {
      console.error("Missing required elements:", missingElements);
      return false;
    }
    return true;
  }
  /** Converts an HTML element to a string representation.
   * This is a utility function to convert an element to a string for easier manipulation.
   * @param {Element} element - The HTML element to convert.
   * @returns {string} The string representation of the element.
   */
  elementToString(element) {
    const wrapper = document.createElement("div");
    wrapper.appendChild(element);
    return wrapper.innerHTML;
  }

  /**
   * Sets up the animated phrase elements for the preloader.
   * This function shuffles the phrases, clears the container, and creates DOM elements for each phrase and its checkmark.
   */
  setupPhrases() {
    this.phrases = this.shuffleArray(this.phrases);
    this.elements.phrasesContainer.innerHTML = ""; // Clear

    this.phrases.forEach((phrase, index) => {
      const div = document.createElement("div");
      div.className = "phrase-item";
      div.style.transform = `translateY(${
        index * this.config.verticalSpacing
      }px)`;

      const span = document.createElement("span");
      span.className = "phrase-text";
      span.textContent = `${phrase}...`;

      const checkSVG = SVGFactory.createCheck(
        index * this.config.verticalSpacing,
        index
      );

      div.appendChild(span);
      div.appendChild(checkSVG);
      this.elements.phrasesContainer.appendChild(div);
    });
  }

  /**
   * Implements an ease-in-out function for smoother animation.
   * @param {number} t - The input value for the easing function.
   * @returns {number} The eased value.
   */

  easeInOut(t) {
    return (Math.sin(t / 200 + 100) + 1) / 2;
  }
  /**
   * Generates HTML of the Preloaded Phrases
   * @returns {string} HTML string containing all phrases with their respective styles and checkmarks.
   */
  createPhrasesHTML() {
    return this.phrases
      .map((phrase, index) => {
        const checkSVG = SVGFactory.createCheck(
          index * this.config.verticalSpacing,
          index
        );
        const checkSVGString = this.elementToString(checkSVG); // Convert SVG to string

        return `
      <div class="phrase-item" style="transform: translateY(${
        index * this.config.verticalSpacing
      }px)">
        <span class="phrase-text">${phrase}...</span>
        ${checkSVGString}
      </div>
    `;
      })
      .join("");
  }
  /**
   * Updates the appearance of the checkmark elements during animation.
   * Adjusts the fill color and alpha based on the animation progress.
   */
  updateChecks() {
    this.checks.forEach((check, i) => {
      const colorChangeBoundary = -i * VERTICAL_SPACING + VERTICAL_SPACING + 15;
      if (this.upwardMovingGroup.currentY < colorChangeBoundary) {
        const alpha = Math.max(
          Math.min(
            1 -
              (this.upwardMovingGroup.currentY - colorChangeBoundary + 15) / 30,
            1
          ),
          0
        );
        check.circle.setAttribute("fill", `rgba(255, 255, 255, ${alpha})`);
        const checkColor = [
          Math.round(255 * (1 - alpha) + 120 * alpha),
          Math.round(255 * (1 - alpha) + 154 * alpha),
        ];
        check.check.setAttribute(
          "fill",
          `rgba(255, ${checkColor[0]}, ${checkColor[1]}, 1)`
        );
      }
    });
  }
  /**
   * Executes a single frame of the preloader animation.
   * Updates element positions and checkmark appearance.
   */
  animate() {
    if (!this.state.isAnimating) return;

    const elapsed = Date.now() - this.state.startTime;
    const progress = Math.min(elapsed / this.config.animationDuration, 1);

    if (progress < 1) {
      this.updateAnimation(progress);
      requestAnimationFrame(this.animate);
    } else {
      this.stop();
    }
  }
  /**
   *
   * Updates the animation state based on the current progress.
   * Moves phrases vertically and updates their completion status.
   * @param {number} progress - The current progress of the animation (0 to 1).
   */
  updateAnimation(progress) {
    const translateY =
      -progress * (this.phrases.length * this.config.verticalSpacing);
    this.elements.phrasesContainer.style.transform = `translateY(${translateY}px)`;

    document.querySelectorAll(".phrase-item").forEach((item, index) => {
      const itemProgress = progress * this.phrases.length - index;
      if (itemProgress > 0) {
        item.classList.add("completed");
      }
    });
  }
  /**
   * Updates the message displayed during the preloader animation.
   */
  updateMessage() {
    this.state.currentPhraseIndex =
      (this.state.currentPhraseIndex + 1) % this.phrases.length;
    this.elements.messageElement.textContent = `${
      this.phrases[this.state.currentPhraseIndex]
    }...`;
  }

  /**
   * Starts the preloader animation.
   */
  start() {
    this.isAnimating = true;
    this.state.startTime = Date.now();
    this.messageInterval = setInterval(
      this.updateMessage,
      this.config.messageInterval
    );
    this.animate();
  }
  /**
   * Stops the preloader animation.
   */
  stop() {
    this.state.isAnimating = false;
    clearInterval(this.messageInterval);

    this.elements.preloader.classList.add("fade-out");
    setTimeout(() => {
      this.elements.preloader.style.display = "none";
      this.elements.contentWrapper.classList.add("show");
      document.body.style.overflow = "visible";
    }, this.config.fadeOutDuration);
  }
}

// UI Controller
/**
 * UIController manages user interface interactions and event listeners for the application.
 * This class provides static methods to initialize UI event handlers and load jokes from the API.
 */
class UIController {
  /**
   * Sets up event listeners for navigation buttons and the joke of the day title.
   * This method attaches animation and click handlers to relevant UI elements.
   */
  static setupEventListeners() {
    // Modal navigation buttons animation
    document.querySelectorAll(".nav-bttn").forEach((button) => {
      button.addEventListener("mouseenter", () =>
        button.classList.add("animate__animated", "animate__pulse")
      );
    });
  }
}

// DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  const preloader = new PreloaderAnimation();
  preloader.initialize();
  // Initialize speech bubble controller
  const speechBubble = new SpeechBubbleController();

  // Setup UI event listeners
  UIController.setupEventListeners();

  setTimeout(() => {
    preloader.stop();

    const page = document.getElementById("page");
    if (page) {
      page.style.display = "none";
    }

    const bodyHide = document.getElementById("body-hide");
    if (bodyHide) {
      bodyHide.style.display = "block";
    }

    document.body.style.overflow = "visible";
  }, PRELOADER_DELAY);
});

class SpeechBubbleController {
  constructor() {
    this.iconElement = document.getElementById('jod-icon');
    this.bubbleElement = null;
    this.jokeContentElement = document.getElementById('joke-content');
    
    this.isHovering = false;
    this.currentJoke = null;
    this.isLoading = false;
    
    this.init();
  }

  init() {
    if (!this.iconElement) {
      console.error('jod-icon element not found');
      return;
    }

    this.createSpeechBubble();
    this.setupEventListeners();
    this.loadInitialJoke();
  }

  createSpeechBubble() {
    // Create speech bubble element
    this.bubbleElement = document.createElement('div');
    this.bubbleElement.className = 'speech-bubble';
    this.bubbleElement.id = 'speech-bubble';
    
    // Create content span
    const contentSpan = document.createElement('span');
    contentSpan.id = 'speech-bubble-content';
    contentSpan.textContent = 'Loading joke...';
    
    this.bubbleElement.appendChild(contentSpan);
    document.body.appendChild(this.bubbleElement);
    
    this.speechContentElement = contentSpan;
  }

  setupEventListeners() {
    // Mouse enter - show bubble and load joke if needed
    this.iconElement.addEventListener('mouseenter', (e) => {
      this.handleMouseEnter(e);
    });

    // Mouse leave - hide bubble
    this.iconElement.addEventListener('mouseleave', () => {
      this.handleMouseLeave();
    });

    // Click - load new joke
    this.iconElement.addEventListener('click', (e) => {
      e.preventDefault();
      this.handleClick();
    });

    // Position bubble on mouse move
    this.iconElement.addEventListener('mousemove', (e) => {
      this.positionBubble(e);
    });
  }

  async handleMouseEnter(e) {
    this.isHovering = true;
    this.positionBubble(e);
    this.showBubble();

    // Update bubble content with current joke or load new one
    if (this.currentJoke) {
      this.speechContentElement.textContent = this.currentJoke;
    } else if (!this.isLoading) {
      await this.loadNewJoke();
    }
  }

  handleMouseLeave() {
    this.isHovering = false;
    this.hideBubble();
  }

  async handleClick() {
    if (!this.isLoading) {
      await this.loadNewJoke();
    }
  }

  showBubble() {
    this.bubbleElement.classList.add('show');
  }

  hideBubble() {
    this.bubbleElement.classList.remove('show');
  }

  positionBubble(e) {
    const iconRect = this.iconElement.getBoundingClientRect();
    const bubbleRect = this.bubbleElement.getBoundingClientRect();
    const viewport = {
      width: window.innerWidth,
      height: window.innerHeight
    };

    // Calculate initial position (above the icon, centered)
    const bubbleWidth = this.bubbleElement.offsetWidth || 250;
    const bubbleHeight = this.bubbleElement.offsetHeight || 80;
    
    let left = iconRect.left + (iconRect.width / 2) - (bubbleWidth / 2);
    let top = iconRect.top - bubbleHeight - 15; // 15px gap

    // Adjust horizontal position if bubble would go off screen
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

    // Adjust vertical position if bubble would go off screen
    if (top < 10) {
      top = iconRect.bottom + 15; // Show below icon instead
    }

    // Apply position
    this.bubbleElement.style.left = `${left}px`;
    this.bubbleElement.style.top = `${top}px`;
  }

  async loadNewJoke() {
    if (this.isLoading) {
      return;
    }
    
    this.isLoading = true;
    this.bubbleElement.classList.add('loading');
    
    if (this.speechContentElement) {
      this.speechContentElement.textContent = 'Loading new joke...';
    }

    try {
      const response = await fetch(API_URL);
      const data = await response.json();
      this.currentJoke = Object.values(data)[0];
      
      // Update both the speech bubble and the main joke content
      if (this.speechContentElement) {
        this.speechContentElement.textContent = this.currentJoke;
      }
      
      // Update the main joke content if it exists
      if (this.jokeContentElement) {
        this.jokeContentElement.textContent = this.currentJoke;
      }
      
    } catch (error) {
      console.error('Error loading joke:', error);
      const errorMessage = 'Failed to load joke. Please try again.';
      
      if (this.speechContentElement) {
        this.speechContentElement.textContent = errorMessage;
      }
      
      if (this.jokeContentElement) {
        this.jokeContentElement.textContent = errorMessage;
      }
      
      this.currentJoke = null;
    } finally {
      this.isLoading = false;
      this.bubbleElement.classList.remove('loading');
    }
  }

  async loadInitialJoke() {
    // Load first joke without showing loading state
    try {
      const response = await fetch(API_URL);
      const data = await response.json();
      this.currentJoke = Object.values(data)[0];
      
      if (this.speechContentElement) {
        this.speechContentElement.textContent = this.currentJoke;
      }
      
      if (this.jokeContentElement) {
        this.jokeContentElement.textContent = this.currentJoke;
      }
    } catch (error) {
      console.error('Error loading initial joke:', error);
      const fallbackJoke = 'Yo momma is so fat that when she walked past the TV, I missed three episodes.';
      this.currentJoke = fallbackJoke;
      
      if (this.speechContentElement) {
        this.speechContentElement.textContent = fallbackJoke;
      }
    }
  }
}
