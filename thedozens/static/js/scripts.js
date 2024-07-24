H.init('5g5kvvlg', { // Get your project ID from https://app.highlight.io/setup
  environment: 'production',
  version: 'commit:abcdefg12345',
  networkRecording: {
      enabled: true,
      recordHeadersAndBody: true,
      urlBlocklist: [

      ],
  },
});

// Initial Joke On Load
$.getJSON("https://the-dozens.onrender.com/insult", response => {
  $("#joke").text(
    Object.values(response)[0]
  );
});
// On-Demand Joke Load
const place_joke = () => {
  $.getJSON("https://the-dozens.onrender.com/insult", response => {
    $("#joke").text(
      Object.values(response)[0]
    );
  });
};
const modalNavButtons = document.querySelectorAll('.nav-bttn')

for (let i = 0; i < modalNavButtons.length; i++) {
  modalNavButtons[i].addEventListener("mouseenter", function () {
    modalNavButtons[i].classList.add("animate__animated animate__pulse");
  });
}
const reportModalTrigger = document.getElementById("reportAJokeTrigger")
const reportAJokeModal = document.getElementById("reportJokeModal")
console.log(modalNavButtons)
var checkmarkIdPrefix = "loadingCheckSVG-";
var checkmarkCircleIdPrefix = "loadingCheckCircleSVG-";
var verticalSpacing = 50;

function shuffleArray(array) {
for (var i = array.length - 1; i > 0; i--) {
    var j = Math.floor(Math.random() * (i + 1));
    var temp = array[i];
    array[i] = array[j];
    array[j] = temp;
}
return array;
}

function createSVG(tag, properties, opt_children) {
var newElement = document.createElementNS("http://www.w3.org/2000/svg", tag);
for(prop in properties) {
newElement.setAttribute(prop, properties[prop]);
}
if (opt_children) {
opt_children.forEach(function(child) {
  newElement.appendChild(child);
})
}
return newElement;
}

function createPhraseSvg(phrase, yOffset) {
var text = createSVG("text", {
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
var check = createSVG("polygon", {
points: "21.661,7.643 13.396,19.328 9.429,15.361 7.075,17.714 13.745,24.384 24.345,9.708 ",
fill: "rgba(255,255,255,1)",
id: checkmarkIdPrefix + index
});
var circle_outline = createSVG("path", {
d: "M16,0C7.163,0,0,7.163,0,16s7.163,16,16,16s16-7.163,16-16S24.837,0,16,0z M16,30C8.28,30,2,23.72,2,16C2,8.28,8.28,2,16,2 c7.72,0,14,6.28,14,14C30,23.72,23.72,30,16,30z",
fill: "white"
})
var circle = createSVG("circle", {
id: checkmarkCircleIdPrefix + index,
fill: "rgba(255,255,255,0)",
cx: 16,
cy: 16,
r: 15
})
var group = createSVG("g", {
transform: "translate(10 " + (yOffset - 20) + ") scale(.9)"
}, [circle, check, circle_outline]);
return group;
}

function addPhrasesToDocument(phrases) {
phrases.forEach(function(phrase, index) {
var yOffset = 30 + verticalSpacing * index;
document.getElementById("phrases").appendChild(createPhraseSvg(phrase, yOffset));
document.getElementById("phrases").appendChild(createCheckSvg(yOffset, index));
});
}

function easeInOut(t) {
var period = 200;
return (Math.sin(t / period + 100) + 1) /2;
}

document.addEventListener("DOMContentLoaded", function(event) {
var phrases = shuffleArray(["Generating witty dialog", "Prepping Insults", "Offending Mothers", "Debasing Fathers", "Irritating Aunts", "Annoying Grandmothers", "Disparaging Grandfathers", "Frustrating Matriarchs",  "Cracking jokes", "Slacking off"]);  addPhrasesToDocument(phrases);
var start_time = new Date().getTime();
var upward_moving_group = document.getElementById("phrases");
upward_moving_group.currentY = 0;
var checks = phrases.map(function(_, i) { 
return {check: document.getElementById(checkmarkIdPrefix + i), circle: document.getElementById(checkmarkCircleIdPrefix + i)};
});
function animateLoading() {
var now = new Date().getTime();
upward_moving_group.setAttribute("transform", "translate(0 " + upward_moving_group.currentY + ")");
upward_moving_group.currentY -= 1.35 * easeInOut(now);
checks.forEach(function(check, i) {
  var color_change_boundary = - i * verticalSpacing + verticalSpacing + 15;
  if (upward_moving_group.currentY < color_change_boundary) {
    var alpha = Math.max(Math.min(1 - (upward_moving_group.currentY - color_change_boundary + 15)/30, 1), 0);
    check.circle.setAttribute("fill", "rgba(255, 255, 255, " + alpha + ")");
    var check_color = [Math.round(255 * (1-alpha) + 120 * alpha), Math.round(255 * (1-alpha) + 154 * alpha)];
    check.check.setAttribute("fill", "rgba(255, " + check_color[0] + "," + check_color[1] + ", 1)");
  }
})
if (now - start_time < 30000 && upward_moving_group.currentY > -710) {
  requestAnimationFrame(animateLoading);
}
}
//animateLoading();
});
/* ------------------
      Preloader
  --------------------*/
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        hideLoader();
        showContent();
    }, 3000);
});     
function hideLoader() {
        $('#phrase_box').fadeOut(900);
        $('#phrases').fadeOut(300)
        $('#phrase_box').css('display', 'none')
        $('#page').fadeOut(1800);
    }

    function showContent() {
        $('#body-hide').fadeIn(1600);
        $('body').css('overflow', 'visible')
      };

function animateJokeOfDayTitle(){
$('#joke-of-day-title').addClass(' animate__animated animate__rubberBand animate__infinite')
 $('#joke-of-day-title').text('Click For Another Joke!')
}

function unanimateJokeOfDayTitle(){
  setTimeout(() => {
$('#joke-of-day-title').remove('animate__animated animate__rubberBand animate__infinite')
$('#joke-of-day-title').text('Joke of the Day')
}, 300)}

 $('#joke-of-day-title-parent').on( "mouseenter", animateJokeOfDayTitle ).on( "mouseleave", unanimateJokeOfDayTitle )
  $('#joke-of-day-title-parent').on( "click", place_joke )