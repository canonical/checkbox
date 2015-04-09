function showHide(what) {
    var heading = document.getElementById(what);
    var contents = document.getElementById(what + "-contents");
    var headingcontents = heading.innerHTML;
    var newcontents;

    if (contents.style.display != "block") {
        newcontents = headingcontents.replace(/[^\x00-\x80]/g, "&#9660;");
        contents.style.display = "block";
    } else {
        newcontents = headingcontents.replace(/[^\x00-\x80]/g, "&#9654;");
        contents.style.display = "none";
    }

    heading.innerHTML = newcontents;
}
