/* ------------------
      Highlight.io Monitoring
  --------------------*/
H.init('5g5kvvlg', { // Get your project ID from https://app.highlight.io/setup
  environment: 'production',
  version: 'commit:abcdefg12345',
  networkRecording: {
      enabled: true,
      recordHeadersAndBody: true,
      urlBlocklist: [],
  },
});
/* ------------------
      END of Highlight.io Monitoring
  --------------------*/

const modalNavButtons = document.querySelectorAll('.nav-bttn');
modalNavButtons.forEach(button => {
  button.addEventListener("mouseenter", () => {
    button.classList.add("animate__animated animate__pulse");
  });
});

const reportModalTrigger = document.getElementById("reportAJokeTrigger");
const reportAJokeModal = document.getElementById("reportJokeModal");
/* ------------------
      Preloader - Rendering
  --------------------*/
const checkmarkIdPrefix = "loadingCheckSVG-";
const checkmarkCircleIdPrefix = "loadingCheckCircleSVG-";
const verticalSpacing = 50;

function shuffleArray(array) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

function createSVG(tag, properties, opt_children) {
  const newElement = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const prop in properties) {
    newElement.setAttribute(prop, properties[prop]);
  }
  if (opt_children) {
    opt_children.forEach(child => {
      newElement.appendChild(child);
    });
  }
  return newElement;
}

function createPhraseSvg(phrase, yOffset) {
  const text = createSVG("text", {
    fill: "white",
    x: 50,
    y: yOffset,
    "font-size": 18,
    "font-family": "Arial"
  });
  text.appendChild(document.createTextNode(phrase + "..."));
  return text;
}

function createCheckSvg(yOffset, index) {
  const check = createSVG("polygon", {
    points: "21.661,7.643 13.396,19.328 9.429,15.361 7.075,17.714 13.745,24.384 24.345,9.708 ",
    fill: "rgba(255,255,255,1)",
    id: checkmarkIdPrefix + index
  });
  const circle_outline = createSVG("path", {
    d: "M16,0C7.163,0,0,7.163,0,16s7.163,16,16,16s16-7.163,16-16S24.837,0,16,0z M16,30C8.28,30,2,23.72,2,16C2,8.28,8.28,2,16,2 c7.72,0,14,6.28,14,14C30,23.72,23.72,30,16,30z",
    fill: "white"
  });
  const circle = createSVG("circle", {
    id: checkmarkCircleIdPrefix + index,
    fill: "rgba(255,255,255,0)",
    cx: 16,
    cy: 16,
    r: 15
  });
  return createSVG("g", {
      transform: `translate(10 ${yOffset - 20}) scale(.9)`
    }, [circle, check, circle_outline]);
}

function addPhrasesToDocument(phrases) {
  const phrasesContainer = document.getElementById("phrases");
  const fragment = document.createDocumentFragment();
  phrases.forEach((phrase, index) => {
    const yOffset = 30 + verticalSpacing * index;
    fragment.appendChild(createPhraseSvg(phrase, yOffset));
    fragment.appendChild(createCheckSvg(yOffset, index));
  });
  phrasesContainer.appendChild(fragment);
}

function easeInOut(t) {
  const period = 200;
  return (Math.sin(t / period + 100) + 1) / 2;
}

document.addEventListener("DOMContentLoaded", () => {
  const phrases = shuffleArray([
    "Generating witty dialog", "Prepping Insults", "Offending Mothers", "Debasing Fathers",
    "Irritating Aunts", "Annoying Grandmothers", "Disparaging Grandfathers", "Frustrating Matriarchs",
    "Cracking jokes", "Slacking off"
  ]);
  addPhrasesToDocument(phrases);
  const start_time = new Date().getTime();
  const upward_moving_group = document.getElementById("phrases");
  upward_moving_group.currentY = 0;
  const checks = phrases.map((_, i) => ({
    check: document.getElementById(checkmarkIdPrefix + i),
    circle: document.getElementById(checkmarkCircleIdPrefix + i)
  }));

  function animateLoading() {
    const now = new Date().getTime();
    upward_moving_group.setAttribute("transform", `translate(0 ${upward_moving_group.currentY})`);
    upward_moving_group.currentY -= 1.35 * easeInOut(now);
    checks.forEach((check, i) => {
      const color_change_boundary = -i * verticalSpacing + verticalSpacing + 15;
      if (upward_moving_group.currentY < color_change_boundary) {
        const alpha = Math.max(Math.min(1 - (upward_moving_group.currentY - color_change_boundary + 15) / 30, 1), 0);
        check.circle.setAttribute("fill", `rgba(255, 255, 255, ${alpha})`);
        const check_color = [Math.round(255 * (1 - alpha) + 120 * alpha), Math.round(255 * (1 - alpha) + 154 * alpha)];
        check.check.setAttribute("fill", `rgba(255, ${check_color[0]},${check_color[1]}, 1)`);
      }
    });
    if (now - start_time < 30000 && upward_moving_group.currentY > -710) {
      requestAnimationFrame(animateLoading);
    }
  }
  //animateLoading();
});

/* ------------------
      Preloader - Logic
  --------------------*/
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    hideLoader();
    showContent();
  }, 3000);
});

function hideLoader() {
  const phraseBox = $('#phrase_box');
  const phrases = $('#phrases');
  const page = $('#page');
  phraseBox.fadeOut(900);
  // phrases.fadeOut(300);
  phraseBox.css('display', 'none');
  page.fadeOut(1800);
}

function showContent() {
  $('#body-hide').fadeIn(1600);
  $('body').css('overflow', 'visible');
}

function animateJokeOfDayTitle() {
  const jokeTitle = $('#joke-of-day-title');
  jokeTitle.addClass('animate__animated animate__rubberBand animate__infinite');
  jokeTitle.text('Click For Another Joke!');
}

function unanimateJokeOfDayTitle() {
  setTimeout(() => {
    const jokeTitle = $('#joke-of-day-title');
    jokeTitle.removeClass('animate__animated animate__rubberBand animate__infinite');
    jokeTitle.text('Joke of the Day');
  }, 300);
}

/* ------------------
     END of Preloader - Logic
  --------------------*/

  /* ------------------
      Joke of Day Jquery Request
  --------------------*/

// Initial Joke On Load
$.getJSON("https://api.yo-momma.net/insult", response => {
  $("#joke-content").text(Object.values(response)[0]);
});

// On-Demand Joke Load
const placeInsult = () => {
  $.getJSON("https://the-dozens.onrender.com/insult", response => {
    $("#joke-content").text(Object.values(response)[0]);
  });
};
const jokeTitleParent = $('#joke-of-day-title-parent');
jokeTitleParent.on("mouseenter", animateJokeOfDayTitle).on("mouseleave", unanimateJokeOfDayTitle);
jokeTitleParent.on("click", placeInsult);

/* ------------------
      END of Joke of Day Jquery Request
        --------------------*/