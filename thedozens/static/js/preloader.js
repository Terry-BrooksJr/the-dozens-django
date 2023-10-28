function domReady(){
    console.log('Dom has Rendered!')
}
function pageload() {

    n = document.getElementById("loadingtime");
  n.innerHTML = "Page load: " + window.performance.domContentLoadedEventEnd + " seconds.";
}
(window.onload = function () {
  pageload();
}),
  setTimeout(function () {
    document.body.className += " loaded";
  }, 1500),
  document.addEventListener
    ? document.addEventListener(
        "DOMContentLoaded",
        function () {
          document.removeEventListener(
            "DOMContentLoaded",
            arguments.callee,
            !1
          ),
            domReady();
        },
        !1
      )
    : document.attachEvent &&
      document.attachEvent("onreadystatechange", function () {
        "complete" === document.readyState &&
          (document.detachEvent("onreadystatechange", arguments.callee),
          domReady());
      });

const yoMamaBrandLogo = document.querySelector('#yo-mama-brand');
yoMamaBrandLogo.addEventListener('click', () => {
    yoMamaBrandLogo.classList.add('animate__animated', 'animate__rubberband');
})
