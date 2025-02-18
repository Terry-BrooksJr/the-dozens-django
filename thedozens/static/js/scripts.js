// Highlight.io Monitoring Configuration
const HIGHLIGHT_CONFIG = {
  environment: 'production',
  version: 'commit:abcdefg12345',
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
  "Generating witty dialog", "Prepping Insults", "Offending Mothers", 
  "Debating Fathers", "Irritating Aunts", "Annoying Grandmothers", 
  "Disparaging Grandfathers", "Frustrating Matriarchs",
  "Cracking jokes", "Slacking off"
];

// Initialize Highlight.io
H.init('5g5kvvlg', HIGHLIGHT_CONFIG);

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
    Object.entries(properties).forEach(([prop, value]) => element.setAttribute(prop, value));
    children.forEach(child => element.appendChild(child));
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
    return this.create("text", {
      fill: "white",
      x: "50",
      y: yOffset.toString(),
      "font-size": "18",
      "font-family": "Arial"
    }, [document.createTextNode(phrase + "...")]);
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
      points: "21.661,7.643 13.396,19.328 9.429,15.361 7.075,17.714 13.745,24.384 24.345,9.708",
      fill: "rgba(255,255,255,1)",
      id: `loadingCheckSVG-${index}`
      });
  
      const circleOutline = this.create("path", {
        d: "M16,0C7.163,0,0,7.163,0,16s7.163,16,16,16s16-7.163,16-16S24.837,0,16,0z M16,30C8.28,30,2,23.72,2,16C2,8.28,8.28,2,16,2 c7.72,0,14,6.28,14,14C30,23.72,23.72,30,16,30z",
        fill: "white"
      });
  
      const circle = this.create("circle", {
        id: `loadingCheckCircleSVG-${index}`,
        fill: "rgba(255,255,255,0)",
        cx: "16",
        cy: "16",
        r: "15"
      });
  
      return this.create("g", {}, [circleOutline, circle, check]);
    }
  }
 /**
 * Controls the preloader animation.
 * This class manages the animation of phrases and checkmarks during the preloading phase.
 */
class PreloaderAnimation {
  constructor(phrases) {
    this.phrases = this.shuffleArray([...phrases]);
    this.startTime = Date.now();
    this.upwardMovingGroup = document.getElementById("phrases");
    this.checks = [];
    this.isAnimating = false;
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
   * Creates and appends the SVG elements for phrases and checkmarks.
   */
  initialize() {
    const fragment = document.createDocumentFragment();
    this.phrases.forEach((phrase, index) => {
      const yOffset = 30 + VERTICAL_SPACING * index;
      fragment.appendChild(SVGFactory.createPhrase(phrase, yOffset));
      fragment.appendChild(SVGFactory.createCheck(yOffset, index));
      
      this.checks.push({
        check: document.getElementById(`loadingCheckSVG-${index}`),
        circle: document.getElementById(`loadingCheckCircleSVG-${index}`)
      });
    });
    
    this.upwardMovingGroup.appendChild(fragment);
    this.upwardMovingGroup.currentY = 0;
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
   * Updates the appearance of the checkmark elements during animation.
   * Adjusts the fill color and alpha based on the animation progress.
   */
  updateChecks() {
    this.checks.forEach((check, i) => {
      const colorChangeBoundary = -i * VERTICAL_SPACING + VERTICAL_SPACING + 15;
      if (this.upwardMovingGroup.currentY < colorChangeBoundary) {
        const alpha = Math.max(Math.min(1 - (this.upwardMovingGroup.currentY - colorChangeBoundary + 15) / 30, 1), 0);
        check.circle.setAttribute("fill", `rgba(255, 255, 255, ${alpha})`);
        const checkColor = [
          Math.round(255 * (1 - alpha) + 120 * alpha),
          Math.round(255 * (1 - alpha) + 154 * alpha)
        ];
        check.check.setAttribute("fill", `rgba(255, ${checkColor[0]}, ${checkColor[1]}, 1)`);
      }
    });
  }
 /**
   * Executes a single frame of the preloader animation.
   * Updates element positions and checkmark appearance.
   */
  animate() {
    if (!this.isAnimating) {
      return;
    }

    const now = Date.now();
    this.upwardMovingGroup.setAttribute("transform", `translate(0 ${this.upwardMovingGroup.currentY})`);
    this.upwardMovingGroup.currentY -= 1.35 * this.easeInOut(now);
    this.updateChecks();

    if (now - this.startTime < ANIMATION_DURATION && this.upwardMovingGroup.currentY > -710) {
      requestAnimationFrame(() => this.animate());
    } else {
      this.isAnimating = false;
    }
  }
  /**
   * Starts the preloader animation.
   */
  start() {
    this.isAnimating = true;
    this.animate();
  }
  /**
   * Stops the preloader animation.
   */
  stop() {
    this.isAnimating = false;
  }
}

// UI Controller
class UIController {
  static setupEventListeners() {
    // Modal navigation buttons animation
    document.querySelectorAll('.nav-bttn').forEach(button => {
      button.addEventListener("mouseenter", () => 
        button.classList.add("animate__animated", "animate__pulse")
      );
    });

    // Joke of the day title animations
    const jokeTitleParent = document.getElementById('joke-of-day-title-parent');
    const jokeTitle = document.getElementById('joke-of-day-title');

    if (jokeTitleParent && jokeTitle) {
      jokeTitleParent.addEventListener("mouseenter", () => {
        jokeTitle.classList.add('animate__animated', 'animate__rubberBand', 'animate__infinite');
        jokeTitle.innerHTML = 'Click <br> For <br> Another Joke!';
      });

      jokeTitleParent.addEventListener("mouseleave", () => {
        setTimeout(() => {
          jokeTitle.classList.remove('animate__animated', 'animate__rubberBand', 'animate__infinite');
          jokeTitle.innerHTML = 'Joke <br> of the <br> Day';
        }, 300);
      });

      jokeTitleParent.addEventListener("click", this.loadNewJoke);
    }
  }

  static async loadNewJoke() {
    try {
      const response = await fetch(API_URL);
      const data = await response.json();
      document.getElementById("joke-content").textContent = Object.values(data)[0];
    } catch (error) {
      console.error("Error loading joke:", error);
    }
  }

  static async loadInitialJoke() {
    try {
      const response = await fetch(API_URL);
      const data = await response.json();
      document.getElementById("joke-content").textContent = Object.values(data)[0];
    } catch (error) {
      console.error("Error loading initial joke:", error);
    }
  }
}

Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Initialize preloader
  const preloader = new PreloaderAnimation(PHRASES);
  preloader.initialize();
  preloader.start();

  // Setup UI event listeners
  UIController.setupEventListeners();
  UIController.loadInitialJoke();

  // Handle preloader hiding
  setTimeout(() => {
    preloader.stop();
    document.getElementById('phrase_box')?.style.display = 'none';
    document.getElementById('page')?.style.display = 'none';
    document.getElementById('body-hide')?.style.display = 'block';
    document.body.style.overflow = 'visible';
  }, PRELOADER_DELAY);
});