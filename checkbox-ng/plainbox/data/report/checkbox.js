function showHide(what) {
    var heading = document.getElementById(what);
    var contents = document.getElementById(what + "-contents");
    var headingcontents = heading.innerHTML;
    var newcontents;

    if (contents.style.display != "block") {
        newcontents = headingcontents.replace("closed", "open");
        contents.style.display = "block";
    } else {
        newcontents = headingcontents.replace("open", "closed");
        contents.style.display = "none";
    }

    heading.innerHTML = newcontents;
}
