var unsupportedInternetExplorer = false;
var showV2 = true;

var readMoreTexts = [];
var changes = [];

var translations = /*getTranslations ? getTranslations() :*/ {};
var translation = {}; // the active translation

var libraryUrl = "/machines/";
var postsLibraryUrl = "/posts/";

/** Returns the translation of the given text. */
function translate(text) {
  var translated = translation[text];
  if (translated) {
    return translated;
  }
  // return "#" + text + "#";
  return text;
}

function createOption(id, text) {
  var option = document.createElement("option");
  option.value = id;
  option.text = text;
  return option;
}

function addOption(node, id, text) {
  node.add(createOption(id, text));
}

function addSplitter(node, text) {
  var option = document.createElement("option");
  option.disabled = true;
  option.text = text ? text : "───────────";
  node.add(option);
}

/** Removes all children nodes. */
function removeAllChildren(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

/** Update translation for the given element ID. */
function translateId(id, text) {
  var element = document.getElementById(id);
  if (element) {
    element.innerHTML = translate(text);
  }
}

function updateFixedTexts() {
  document.title = translate("Machine Library");

  translateId("headerTitle", "Machine Library");
  translateId("headerIntro", "This is the place to find generic CNC machines.");

  var element = document.getElementById("search");
  if (element) {
    element.setAttribute("placeholder", translate("Find your machine here"));
  }

  element = document.getElementById("type");
  if (element) {
    removeAllChildren(element);
    addOption(element, "ANY", translate("Any type"));
    addOption(element, "MILLING", translate("Milling"));
    addOption(element, "TURNING", translate("Turning"));
    addOption(element, "MILL/TURN", translate("Mill / Turn"));
    addOption(element, "JET", translate("Waterjet / Laser / Plasma"));
    addOption(element, "ADDITIVE", translate("Addititve"));
    addOption(element, "INSPECTION", translate("Inspection"));
  }

  element = document.getElementById("vendor");
  if (element) {
    removeAllChildren(element);
    addOption(element, "", translate("Any vendor"));
    for (i in vendors) {
      var vendor = vendors[i];
      addOption(element, vendor, vendor);
    }
  }
}

function dumpTranslation() {
  var translate = document.getElementById("translate");
  if (!translate) {
    return;
  }
  var text = "";
  for (var key in translationDanish) {
    text += key + "<br/>";
  }
  translate.innerHTML = text;
}

/** Load translation from JSON file. */
function loadTranslation(code) {
  return load(libraryUrl + "translations/" + code + ".json");
}

/** Select the given language by id. */
function selectTranslation(language) {
  translation = {};
  var t = translations[language];
  if (t) {
    translation = t;
  }
  var i = language.indexOf("-");
  if (i >= 0) {
    language = language.substr(0, i);
  }
  t = translations[language];
  if (t) {
    translation = t;
  }
  updateFixedTexts();
  // dumpTranslation();
  onResetSearch();
}

/** Registers the given language. */
function addLanguage(id, description) {
  var translation = translations[id];
  if (!translation || Object.keys(translation).length == 0) {
    if (false) {
      translation = loadTranslation(id);
      if (!translation) {
        return;
      }
      translations[id] = translation;
    } else {
      return;
    }
  }
  var select = document.getElementById("selectLanguage");
  if (select) {
    var newOption = document.createElement('option');
    newOption.value = id;
    newOption.innerText = description;
    select.appendChild(newOption);
  }
}

/** Registers all languages. */
function addLanguages() {
  addLanguage('zh-CHS', 'Chinese (Simplified)');
  addLanguage('zh-CHT', 'Chinese (Traditional)');
  addLanguage('da', 'Danish');
  addLanguage('fi', 'Finnish');
  addLanguage('fr', 'French');
  addLanguage('de', 'German');
  addLanguage('it', 'Italian');
  addLanguage('ja', 'Japanese');
  addLanguage('ko', 'Korean');
  addLanguage('po', 'Polish');
  addLanguage('es', 'Spanish');
  addLanguage('sv', 'Swedish');
}

/** Returns the default language. */
function getDefaultLanguage() {
  return "en";
}

/** Handler for language selection. */
function selectLanguage(object) {
  var select = document.getElementById("selectLanguage");
  if (select) {
    selectTranslation(select.options[select.selectedIndex].value);
    updateSearchResult();
  }
}

/** Returns true if mobile. */
function isMobile() {
  if (navigator.userAgent.match(/Android/i) ||
    navigator.userAgent.match(/webOS/i) ||
    navigator.userAgent.match(/iPhone/i) ||
    // navigator.userAgent.match(/iPad/i) ||
    navigator.userAgent.match(/iPod/i) ||
    navigator.userAgent.match(/BlackBerry/i) ||
    navigator.userAgent.match(/Windows Phone/i)) {
    return true;
  } else {
    return false;
  }
}

var mobile = isMobile();

/** Load JSON file from url. */
function load(url) {
  var http = new XMLHttpRequest();
  try {
    http.open("GET", url, false);
    http.onreadystatechange = function () {
      if (this.readyState == 4) {
        // console.log("HTTP RESPONSE: " + this.status + " " + this.responseText);
      }
    };
    http.send();
    if (http.status != 200) {
      return;
    }
    var response = http.responseText;
    if (!response) {
      return undefined;
    }
    var data = JSON.parse(response);
    return data;
  } catch (e) {
    return undefined; // failed
  }
}

/** Loads data from url. */
function loadWithCaching(url, id, timeout) {
  try {
    var data;
    if (typeof (Storage) !== "undefined") {
      var now = (new Date()).getTime();
      try {
        var cachedTime = sessionStorage.getItem("cache-time-" + id);
        var cachedData = sessionStorage.getItem("cache-data-" + id);
        if (cachedData && cachedTime && ((now - cachedTime) < timeout * 1000)) {
          data = cachedData; // use cache
        }
      } catch (e) {
        // ignore        
      }
    }

    if (data === undefined) {
      // var started = (new Date()).getTime();
      var http = new XMLHttpRequest();
      try {
        http.open("GET", url, false);
        http.onreadystatechange = function () {
          if (this.readyState == 4) {
            // console.log("HTTP RESPONSE: " + this.status + " " + this.responseText);
          }
        };
        http.send();
        // var elapsed = (new Date()).getTime() - started;
        // if (typeof(Storage) !== "undefined") { // cache result
        //   sessionStorage.setItem("cache-load-time-" + id, elapsed);
        // }          
        if (http.status == 200) {
          var response = http.responseText;
          if (typeof (Storage) !== "undefined") { // cache result
            sessionStorage.setItem("cache-time-" + id, (new Date()).getTime());
            sessionStorage.setItem("cache-data-" + id, response);
          }
          data = response;
        }
      } catch (e) {
        // ignore
      }
    }
    return data;
  } catch (e) {
    return undefined;
  }
}

/** Loads available machines. */
function loadMachines() {
  try {
    var data = loadWithCaching(libraryUrl + "machines/machines.json", "machines", 1 * 60); // every 5 minutes
    var machines = JSON.parse(data);

    // update cache
    for (var i in machines) {
      var m = machines[i];
      m.c = m.machining ? m.machining.split(" ") : [];
      //m.dt = parseDateTime(m.datetime);
    }
    return machines;
  } catch (e) {
    return [];
  }
}

/** Loads available posts. */
function loadPosts() {
  try {
    var data = loadWithCaching(postsLibraryUrl + "posts/posts-website.json", "posts", 5 * 60); // every 5 minutes
    var posts = JSON.parse(data);

    // update cache
    for (var i in posts) {
      var p = posts[i];
      p.c = p.capabilities ? p.capabilities.split(" ") : [];
      p.dt = parseDateTime(p.datetime);
    }
    return posts;
  } catch (e) {
    return [];
  }
}

/** Loads stats. */
function loadStats() {
  try {
    var data = loadWithCaching(libraryUrl + "stats.php", "stats", 1 * 60); // every minute
    return JSON.parse(data);
  } catch (e) {
    console.log("ERROR: Failed to load stats.");
    return [];
  }
}

var WEIGHT_MODEL = 100.0;
var WEIGHT_DESCRIPTION = 50.0;
var WEIGHT_VENDOR = 10.0;
var WEIGHT_LONG_DESCRIPTION = 2.0;
var WEIGHT_FILENAME = 0.25;
var WEIGHT_LAST_WEEK = 0.1;
var WEIGHT_LAST_MONTH = 0.01;
var WEIGHT_LAST_YEAR = 0.001;
var WEIGHT_HITS = 0.0001; // over total number of hits
var WEIGHT_DOWNLOADS = 0.0001; // over total number of downloads

function cleanSearchText(text) {
  return text.trim();
}

function date(seconds) {
  if (seconds == undefined) {
    return "";
  }
  var d = new Date(seconds * 1000);
  return d.toLocaleString();
  // return d.toLocaleDateString() + " " + d.toLocaleTimeString();
}

/** Format time. */
function time(seconds) {
  if (seconds == undefined) {
    return "";
  }
  if (seconds <= 0) {
    return "0 " + translate("seconds");
  }
  if (seconds < 5) {
    return seconds.toFixed(3) + " " + translate("seconds");
  }
  if (seconds >= 0) {
    seconds = Math.round(seconds);
    if (seconds < 1) {
      return "1 " + translate("second");
    }
    var s = ~~seconds;
    var m = ~~(s / 60);
    var h = ~~(m / 60);
    var d = ~~(h / 24);
    var result = "";
    if (d > 0) {
      if (d == 1) {
        result = result + (d) + " " + translate("day") + " ";
      } else {
        result = result + (d) + " " + translate("days") + " ";
      }
    }
    if ((h % 24) > 0) {
      if (h % 24 == 1) {
        result = result + (m % 60) + " " + translate("hour") + " ";
      } else {
        result = result + (h % 24) + " " + translate("hours") + " ";
      }
    }
    if ((m % 60) > 0) {
      if (m % 60 == 1) {
        result = result + (m % 60) + " " + translate("minute") + " ";
      } else {
        result = result + (m % 60) + " " + translate("minutes") + " ";
      }
    }
    if ((s % 60) > 0) {
      if (s % 60 == 1) {
        result = result + (m % 60) + " " + translate("second") + " ";
      } else {
        result = result + (s % 60) + " " + translate("seconds") + " ";
      }
    }
    return result;
  }
  return "" + (seconds * 1.0).toFixed(0) + " s";
}

/** Format as byte space. */
function space(value) {
  if (value < 1024) {
    return "" + Math.round(value) + " b";
  } else if (value < 1024 * 1024) {
    return "" + Math.round(value / 1024.0 * 100) / 100.0 + " kb";
  } else if (value < 1024 * 1024 * 1024) {
    return "" + Math.round(value / 1024.0 / 1024.0 * 100) / 100.0 + " Mb";
  } else if (value < 1024 * 1024 * 1024 * 1024) {
    return "" + Math.round(value / 1024.0 / 1024.0 / 1024.0 * 100) / 100.0 + " Gb";
  } else {
    return "" + Math.round(value / 1024.0 / 1024.0 / 1024.0 / 1024.0 * 100) / 100.0 + " Tb";
  }
}

/** Format as bandwidth. */
function rate(value) {
  if (value < 1024) {
    return "" + Math.round(value) + " b/s";
  } else if (value < 1024 * 1024) {
    return "" + Math.round(value / 1024.0 * 100) / 100.0 + " kb/s";
  } else if (value < 1024 * 1024 * 1024) {
    return "" + Math.round(value / 1024.0 / 1024.0 * 100) / 100.0 + " Mb/s";
  } else if (value < 1024 * 1024 * 1024 * 1024.0) {
    return "" + Math.round(value / 1024.0 / 1024.0 / 1024.0 * 100) / 100.0 + " Gb/s";
  } else {
    return "" + Math.round(value / 1024.0 / 1024.0 / 1024.0 / 1024.0 * 100) / 100.0 + " Tb/s";
  }
}

function showOverlay() {
  var element = document.getElementById("overlay_background");
  if (element) {
    element.style.display = (element.style.display == "block") ? "none" : "block";
  }
  element = document.getElementById("overlay");
  if (element) {
    element.style.display = (element.style.display == "block") ? "none" : "block";
  }
}

/** Subscibe some buttons on Download dialog */
function subscribeDownload() {
  // Selecting CAM selector radio buttons
  const camButtons = document.getElementsByName("cam_selector");

  // Adding event to all of them
  camButtons.forEach(button => {
    button.onclick = () => {
      if (button.checked) {
        const details = document.getElementById("download_details");
        const legacy = button.value == "legacy";
        details.style.display = legacy ? "flex" : "none";
      }
    }
  })
}

/** Show / hide download dialog */
function toggleDownloadDialog() {
  var element = document.getElementById("dialog_background");
  if (element) {
    element.style.display = (element.style.display == "flex") ? "none" : "flex";
  }
}

/** Machine selected for downloading */
var selectedMachine;

/** Returns true, if post is compatiable with machine by checking their capabilities */
function isPostCompatiableWithMachine(post, machine) {
  // Returns true, if there is intersection between machine and post capabilities
  for (var i in machine.c) {
    if (post.c.includes(machine.c[i])) {
      return true;
    }
  }
  return false;
}

/** Returns post selected for downloading */
function selectedPost() {
  var postSelector = document.getElementById("post_selector");
  return postSelector.value;
}

/** Returns post revison number selected for downloading */
function selectedRevision() {
  var revisionSelector = document.getElementById("revision_selector");
  return revisionSelector.value;
}

/** Cached post revision changes */
var cachedChanges = [];
/** First post revision that supports machine v2 */
const firstPostRevision = 45805;

/** Fill revisions selector for selected post */
function populateRevisions(postName) {
  var revisionSelector = document.getElementById("revision_selector");
  removeAllChildren(revisionSelector);
  if (!(postName in cachedChanges)) {
    cachedChanges[postName] = load(postsLibraryUrl + "changes.php?name=" + postName);
  }
  const data = cachedChanges[postName];
  if (!data) {
    return;
  }
  const minRev = [];
  var previousMinimumRevision = 0;
  for (var i in data) {
    const entry = data[i];
    // Post revision
    const revision = entry.revision;
    // Minimum post processor revision required to run the post
    var minimumRevision = entry.minimumRevision;
    // Clip by first revision of machine v2
    if (minimumRevision < firstPostRevision) {
      minimumRevision = firstPostRevision;
    }
    if (minimumRevision != previousMinimumRevision) {
      previousMinimumRevision = minimumRevision;
      addOption(revisionSelector, revision, minimumRevision);
    }
  }
}

/** Called on post selection changed */
function onPostSelected() {
  populateRevisions(selectedPost());
}

/**
 * Add posts from the machine.
 * Returns list of added posts names
*/
function addMachinePosts(postSelector, machine) {
  var addedPosts = [];
  for (var i in machine.posts) {
    var machinePost = machine.posts[i];
    // Remove file extension
    var postName = machinePost.file.split('.')[0];
    var text = machinePost.id;
    if (text == "default") {
      for (var j in posts) {
        var post = posts[j];
        if (post.filename == postName) {
          text = post.description;
        }
      }
    }
    addOption(postSelector, postName, text);
    addedPosts.push(postName);
  }
  return addedPosts;
}

/** Add all posts compatiable with machine */
function addCompatiablePosts(postSelector, machine, excluded) {
  for (var i in posts) {
    var post = posts[i];

    // Skip hidden posts
    if (post.hidden) {
      continue;
    }
    // Skip incompatiable posts
    if (!isPostCompatiableWithMachine(post, machine)) {
      continue;
    }
    // Skip already included posts (from machine itself)
    if (excluded.includes(post.filename)) {
      continue;
    }
    // Add post finally
    addOption(postSelector, post.filename, post.description);
  }
}

/** Fill posts selector for selected machine */
function populatePosts(machine) {
  var postSelector = document.getElementById("post_selector");
  removeAllChildren(postSelector);
  addSplitter(postSelector, "─── Preconfigured posts ───");

  // Add options from machine first
  var addedPosts = addMachinePosts(postSelector, machine);

  // Split
  addSplitter(postSelector, "─── All posts ───");

  // Add the rest of compatiable posts
  addCompatiablePosts(postSelector, machine, addedPosts);
}

/** Show download dialog by machine name */
function showDownload(machineName) {
  // Set selected machine
  for (var i in machines) {
    var machine = machines[i];
    if (machine.filename == machineName) {
      selectedMachine = machine;
      break;
    }
  }
  // Update posts list
  populatePosts(selectedMachine);
  // Update revisions list
  onPostSelected();
  // Show dialog
  toggleDownloadDialog();
}

/** Cloase machine download dialog */
function closeDownloadDialog() {
  toggleDownloadDialog();
}

/** Download button handler */
function onDownload() {
  var downloadLink;
  var fusion = document.getElementById("fusion");
  if (fusion.checked) {
    downloadLink = libraryUrl + "download.php?name=" + encodeURIComponent(selectedMachine.filename);
  } else {
    downloadLink = libraryUrl + "download-post-archive.php?" + 
      "machine=" + encodeURIComponent(selectedMachine.filename) + 
      "&post=" + encodeURIComponent(selectedPost() + ".cps");
    var revision = selectedRevision();
    if (revision) {
      downloadLink += "&revision=" + revision;
    }
  }
  
  window.open(downloadLink);
  closeDownloadDialog();
}

var machines = [];
var posts = [];
var vendors = [];
var totalDownloads = 1;
var toalHits = 1;

function encodeHTML(text) {
  var length = text.length;
  var encode = false;
  var start = 0;
  for (var i = 0; i < length; ++i) {
    var ch = text[i].charCodeAt();
    if ((ch < 65) || (ch > 127) || ((ch > 90) && (ch < 97))) {
      encode = true;
      break;
    }
  }
  if (!encode) {
    return text;
  }
  var result = text.substr(0, start);
  for (var i = start; i < length; ++i) {
    var ch = text[i].charCodeAt();
    if ((ch < 65) || (ch > 127) || ((ch > 90) && (ch < 97))) {
      result += '&#' + ch + ';';
    } else {
      result += text[i];
    }
  }
  return result;
}

var filterType = "";

function onType() {
  var element = document.getElementById("type");
  filterType = element.value;
  if (filterType == "ANY") {
    filterType = undefined;
  }
  // console.log("Filter by type: " + filterType);
  updateSearchResult();
}

var filterAge = 0;

function onAge() {
  var element = document.getElementById("age");
  switch (element.value) {
    case "any time":
      filterAge = 0;
      break;
    case "past day":
      filterAge = 1;
      break;
    case "past week":
      filterAge = 7;
      break;
    case "past month":
      filterAge = 30;
      break;
    case "past year":
      filterAge = 365;
      break;
    default:
      filterAge = 0;
  }
  // console.log("Filter by days: " + filterAge);
  updateSearchResult();
}

var filterVendor = "";

function onVendor() {
  var element = document.getElementById("vendor");
  filterVendor = element.value;
  // console.log("Filter by vendor: " + filterVendor);
  updateSearchResult();
}

var filterSimulation = false;
function onSimulationReady() {
  var element = document.getElementById("simulation");
  filterSimulation = element.checked;
  updateSearchResult();
}

var previousSearchText;

function doSearch() {
  var searchElement = document.getElementById("search");
  if (!searchElement) {
    return;
  }
  var searchText = cleanSearchText(searchElement.value);
  if (searchText === previousSearchText) {
    return;
  }
  updateSearchResult();
}

function onSearch() {
  setTimeout(doSearch, 250);
}

function getTypeDescription(machine) {
  var capabilities = machine.c;
  if ((capabilities.indexOf("MILLING") >= 0) && (capabilities.indexOf("TURNING") >= 0)) {
    return translate("Mill / Turn");
  }
  if ((capabilities.indexOf("MILLING") >= 0) && (capabilities.indexOf("JET") >= 0)) {
    return translate("Mill and Waterjet / Laser / Plasma");
  }
  if (capabilities.indexOf("MILLING") >= 0) {
    return translate("Milling");
  }
  if (capabilities.indexOf("TURNING") >= 0) {
    return translate("Turning");
  }
  if (capabilities.indexOf("JET") >= 0) {
    return translate("Waterjet / Laser / Plasma");
  }
  if (capabilities.indexOf("ADDITIVE") >= 0) {
    return translate("Additive");
  }
  if (capabilities.indexOf("INSPECTION") >= 0) {
    return translate("Inspection");
  }
  return translate("Unknown");
}

function parseDateTime(text) {
  var dt = text.split(" ");
  var d = dt[0].split("-");
  var yy = d[0];
  var mm = d[1] - 1;
  var dd = d[2];
  var t = dt[1].split(":");
  var h = t[0];
  var m = t[1];
  var s = t[2];
  return new Date(yy, mm, dd, h, m, s);
}

function getSince(dt) {
  var now = new Date().getTime();
  var delta = now - dt.getTime();
  delta = delta / 1000.0 / 60 / 60;
  if (delta < 1) {
    return translate("Less than an hour ago");
  }
  if (delta < 12) {
    return translate("%1 hours ago").replace("%1", Math.ceil(delta));
  }
  delta /= 24;
  if (delta <= 1) {
    return translate("A day ago");
  }
  if (delta > 365) {
    return translate("More than a year ago");
  }
  return translate("%1 days ago").replace("%1", Math.ceil(delta));
}

function sortByRating(a, b) {
  if (a.rating < b.rating) {
    return 1;
  }
  if (a.rating > b.rating) {
    return -1;
  }
  return 0;
}

function isSeparator(ch) {
  return (ch == " ") || (ch == "\t") || (ch == "\r") || (ch == "\n") || (ch == ".") || (ch == ",") || (ch == "(") || (ch == ")");
}

function weight(i, text, searchText) {
  return searchText.length + ((i == 0) || isSeparator(text[i - 1]) ? 1 : 0) +
    ((((i + searchText.length) >= text.length) || isSeparator(text[i + searchText.length])) ? 1 : 0);
}

function getRating(record, searchText) {
  var rating = 0;
  if (searchText) {
    var i = 0;
    // TAG: split by whitespace and compare separately
    if (record.model) {
      i = record.model.toLowerCase().indexOf(searchText);
      if (i >= 0) {
        rating += WEIGHT_MODEL * weight(i, record.model, searchText);
      }
    }
    if (record.description) {
      i = record.description.toLowerCase().indexOf(searchText);
      if (i >= 0) {
        rating += WEIGHT_DESCRIPTION * weight(i, record.description, searchText);
      }
    }
    if (record.longDescription) {
      i = record.longDescription.toLowerCase().indexOf(searchText);
      if (i >= 0) {
        rating += WEIGHT_LONG_DESCRIPTION * weight(i, record.longDescription, searchText);
      }
    }
    if (record.filename) {
      i = record.filename.toLowerCase().indexOf(searchText);
      if (i >= 0) {
        rating += WEIGHT_FILENAME * weight(i, record.filename, searchText);
      }
    }
    if (record.vendor) {
      i = record.vendor.toLowerCase().indexOf(searchText);
      if (i >= 0) {
        rating += WEIGHT_VENDOR * weight(i, record.vendor, searchText);
      }
    }
  }
  if (rating > 0) {
    if (record.description) {
      rating += 0.001 * 1.0 / record.description.length; // prefer shortest description
    }
    if (record.hits) {
      rating += WEIGHT_HITS * record.hits * 1.0 / totalHits;
    }
    if (record.count) {
      rating += WEIGHT_DOWNLOADS * record.count * 1.0 / totalDownloads;
    }
  }
  return rating;
}

/** Show more text. */
function readMore(element, index) {
  if (!element) {
    return;
  }
  var text = readMoreTexts[index];
  if (text) {
    element.style.display = "none";
    element.parentNode.innerHTML = text;
    // element.innerHTML = text;
  }
}

var cachedChanges = {};

function xmlEscape(text) {
  var result = "";
  for (var i = 0; i < text.length; ++i) {
    var c = text.charAt(i);
    switch (c) {
      case '<': result += "&lt;"; break;
      case '>': result += "&gt;"; break;
      case '\"': result += "&quot;"; break;
      case '&': result += "&amp;"; break;
      case '\'': result += "&apos;"; break;
      default:
        if (c > 0x7e) {
          result += "&#" + int(c) + ";";
        } else {
          result += c;
        }
    }
  }
  return result;
}

/** Encode machine ID. */
function encodeMachineId(text) {
  return text.replace(/ /g, "_");
}

/** Decode machine ID. */
function decodeMachineId(text) {
  return text.replace(/_/g, " ");
}

/** Returns the list of words to be searched for. */
function getSearchWords(text) {
  var words = [];
  var quoted = false;
  var current = "";
  for (var j = 0; j < text.length; ++j) {
    var ch = text[j];
    if (ch == "\"") { // quote
      if (quoted) {
        quoted = false; // end - but not new word
      } else {
        if (!current) {
          quoted = true; // begin
        } else {
          current += "\"";
        }
      }
    } else if (ch == " ") { // new word
      if (quoted) {
        current += ch; // include spaces
      } else {
        if (current) { // only words
          words.push(current);
          current = "";
        }
      }
    } else {
      current += ch;
    }
  }
  if (quoted) { // not terminated
    current = "\"" + current; // look for "
    var split = current.split(" ");
    for (var j = 0; j < split.length; ++j) {
      var word = split[j].trim();
      if (word) {
        words.push(word);
      }
    }
    current = "";
  }
  if (current) { // only words
    words.push(current);
  }
  return words;
}

/** Add help text to the element */
function addHelpTextToElement(element) {
  var html = "";
  html += "<table><tr><td class=\"empty\" colspan=\"2\" style=\"white-space: wrap;\">";
  html += translate("Enter some text and the matching machines will be listed in order of relevance.");
  html += "</br>";
  html += "</br>";
  html += translate("You can use the following advanced search keywords to limit your search further.");
  html += "</br></br>";
  html += "vendor:TEXT Search for a specific vendor</br>";
  html += "description:TEXT Search for a specific description</br>";
  html += "version:NUMBER Search for a specific version</br>";
  html += "version:NUMBER- Search for all versions from the given version</br>";
  html += "version:-NUMBER Search for all versions up to the given version</br>";
  html += "version:NUMBER-NUMBER Search for all versions within the given range</br>";
  html += "days:NUMBER Search for all machines updated within the given number of days</br>";
  html += "downloads:NUMBER Search for all machines with the given minimum number of downloads</br>";
  html += "machineid:TEXT Search for a specific machine with the given ID</br>";
  html += "editable Search for simple machines that support editing</br>";
  html += "</td></tr><table>";
  element.innerHTML = html;
}

/** Get the search criteria details from the search text */
function getSearchCriteriaFromText(searchText) {
  var description;
  var machineId;
  var vendor;
  var days;
  var downloads;
  var versionMinimum;
  var versionMaximum;
  var editable;

  var words = getSearchWords(searchText);
  searchText = "";
  for (var i in words) {
    var w = words[i];
    if (w.indexOf("vendor:") === 0) {
      vendor = w.substr("vendor:".length).toLowerCase();
      continue;
    }
    if (w.indexOf("description:") === 0) {
      description = w.substr("description:".length).toLowerCase();
      continue;
    }
    if (w.indexOf("editable") === 0) {
      editable = true;
      continue;
    }
    if (w.indexOf("machineid:") === 0) {
      machineId = decodeMachineId(w.substr("machineid:".length)); // keep case
      continue;
    }
    if (w.indexOf("days:") === 0) {
      var value = w.substr("days:".length).toLowerCase();
      var daysInt = parseInt(value, 10);
      if (daysInt) {
        days = daysInt;
      }
      continue;
    }
    if (w.indexOf("downloads:") === 0) {
      var value = w.substr("downloads:".length).toLowerCase();
      var downloadsInt = parseInt(value, 10);
      if (downloadsInt) {
        downloads = downloadsInt;
      }
      continue;
    }
    if (w.indexOf("version:") === 0) {
      var value = w.substr("version:".length).toLowerCase();
      var index = value.indexOf("-");
      var version = parseInt(value, 10);
      if ((index < 0) && version) {
        versionMinimum = version;
        versionMaximum = version;
      } else {
        var first = parseInt(value.substr(0, index), 10);
        var last = parseInt(value.substr(index + 1), 10);
        versionMinimum = (index > 0) ? first : undefined;
        versionMaximum = (index >= 0) ? last : undefined;
      }
      continue;
    }
    if (searchText) {
      searchText += " ";
    }
    searchText += w.toLowerCase();
  }
  return {
    description,
    machineId,
    vendor,
    days,
    downloads,
    versionMinimum,
    versionMaximum,
    editable,
    searchText
  };
}

/** Is the machine filter-type a machine capability */
function isFilterTypeInCapabilities(capabilities) {
  switch (filterType) {
    case "ANY":
      return true;
    case "MILLING":
      if (capabilities.indexOf("MILLING") < 0) {
        return false;
      }
      if (capabilities.indexOf("TURNING") >= 0) {
        return false;
      }
      return true;
    case "TURNING":
      if (capabilities.indexOf("TURNING") < 0) {
        return false;
      }
      return true;
    case "MILL/TURN":
      if ((capabilities.indexOf("MILLING") < 0) || (capabilities.indexOf("TURNING") < 0)) {
        return false;
      }
      return true;
    case "JET":
      if (capabilities.indexOf("JET") < 0) {
        return false;
      }
      return true;
    case "ADDITIVE":
      if (capabilities.indexOf("ADDITIVE") < 0) {
        return false;
      }
      return true;
    case "INSPECTION":
      if (capabilities.indexOf("INSPECTION") < 0) {
        return false;
      }
      return true;
    default:
      console.log("Invalid filter type");
      return true;
  }
}

function isSimulationReadyModel(machine) {
  return !!machine.simulationModel;
}

/** Return the machines which meet the search criteria */
function searchMachines(searchCriteria) {
  var description = searchCriteria.description;
  var machineId = searchCriteria.machineId;
  var vendor = searchCriteria.vendor;
  var days = searchCriteria.days;
  var downloads = searchCriteria.downloads;
  var versionMinimum = searchCriteria.versionMinimum;
  var versionMaximum = searchCriteria.versionMaximum;
  var editable = searchCriteria.editable;
  var searchText = searchCriteria.searchText;

  var now = (new Date()).getTime();
  var filterVendorLower = filterVendor ? filterVendor.toLowerCase() : "";
  var searchResults = [];

  for (var i in machines) {
    var machine = machines[i];

    machine.rating = 0;

    if (!showV2 && machine.filename.endsWith(".mch")) {
      continue;
    }

    if (machine.hidden && (machine.filename != machineId)) {
      continue;
    }

    if (editable && !machine.editable) {
      continue;
    }

    // filter
    if (filterType && !isFilterTypeInCapabilities(machine.c)) {
      continue;
    }

    if (filterSimulation && !isSimulationReadyModel(machine)) {
      continue;
    }

    if (filterAge > 0) {
      var dt = machine.dt.getTime();
      if ((now - dt) > (filterAge * 24 * 60 * 60 * 1000.0)) {
        continue;
      }
    }

    if (filterVendorLower) {
      if (!machine.vendor || (machine.vendor.toLowerCase() != filterVendorLower)) {
        continue;
      }
    }

    if (days) {
      var dt = machine.dt.getTime();
      if ((now - dt) > (days * 24 * 60 * 60 * 1000.0)) {
        continue;
      }
    }

    if (machineId) {
      if (machine.filename != machineId) { // exact match required
        continue;
      }
    }

    if (editable) {
      if (!machine.editable) {
        continue;
      }
    }

    if (downloads) {
      if (!machine.count || (machine.count < downloads)) {
        continue;
      }
    }

    if (description) {
      if (!machine.description || (machine.description.toLowerCase().indexOf(description) < 0)) {
        continue;
      }
    }

    if (vendor) {
      if (!machine.vendor || (machine.vendor.toLowerCase().indexOf(vendor) < 0)) {
        continue;
      }
    }

    if (versionMinimum || versionMaximum) {
      if (machine.version) {
        if (versionMinimum && versionMaximum) {
          if (!((machine.version >= versionMinimum) && (machine.version <= versionMaximum))) {
            continue;
          }
        } else if (versionMinimum) {
          if (machine.version < versionMinimum) {
            continue;
          }
        } else if (versionMaximum) {
          if (machine.version > versionMaximum) {
            continue;
          }
        }
      } else {
        continue;
      }
    }

    // search
    if (searchText) {
      var rating = getRating(machine, searchText);
      machine.rating = rating;
      if (rating <= 0) {
        continue;
      }
    } else {
      var rating = 0;
      if (machine.description) {
        rating += WEIGHT_DOWNLOADS * 0.1 * 1.0 / machine.description.length; // prefer shortest description
      }
      if (machine.hits) {
        rating += WEIGHT_HITS * machine.hits * 1.0 / totalHits;
      }
      if (machine.count) {
        rating += WEIGHT_DOWNLOADS * machine.count * 1.0 / totalDownloads;
      }
      machine.rating = rating;
    }

    searchResults.push(machine);
  }
  return searchResults;
}

/** Get the machine image tag */
function getImageTag(machine) {
  var imageUrl = machine.thumbnail ? (libraryUrl + "machines/" + machine.thumbnail) : "";
  if (!imageUrl) {
    var capabilities = machine.c;
    if ((capabilities.indexOf("MILLING") >= 0) &&
        (capabilities.indexOf("TURNING") >= 0)) {
      imageUrl = libraryUrl + "graphics/mill_turn.png";
    } else if (capabilities.indexOf("JET") >= 0) {
      imageUrl = libraryUrl + "graphics/jet.png";
    } else if (capabilities.indexOf("MILLING") >= 0) {
      imageUrl = libraryUrl + "graphics/milling.png";
    } else if (capabilities.indexOf("TURNING") >= 0) {
      imageUrl = libraryUrl + "graphics/turning.png";
    } else if (capabilities.indexOf("ADDITIVE") >= 0) {
      imageUrl = libraryUrl + "graphics/additive.png";
    } else if (capabilities.indexOf("INSPECTION") >= 0) {
      imageUrl = libraryUrl + "graphics/inspection.png";
    } else {
      imageUrl = libraryUrl + "graphics/unknown.png";
    }
  }
  return imageUrl ? ("<img src=\"" + imageUrl + "\" width=\"160\" height=\"140\"/>") : "";
}

/** Get the machine heading section */
function getMachineHeadingSection(title, machine) {
  var htmlText = "";
  if(mobile) {
    htmlText += "<tr class=\"post mobile\"><td colspan=\"2\" style=\"vertical-align:middle\"><span class=\"title\">" + title + "</span><br>";
  } else {
    htmlText += "<tr><td style=\"vertical-align:middle\"><span class=\"title\">" + title + "</span><br>";
  }

  //showDownload
  linkText = "";
  if (machine.filename.endsWith(".mch")) {
    linkText = "href=\"javascript:showDownload('" + machine.filename + "');\"";
  } else {
    linkText = "href='" + libraryUrl + "download.php?name=" + encodeURIComponent(machine.filename) + "'";
  }
  htmlText += "<a data-ga=\"['_trackEvent', 'CAM Posts Library', 'Download Link', 'File: " + machine.filename + "', 2, false]\" class=\"title download_link\" " + linkText + ">"+ translate("Download") + "</a>";

  if (machine.machineConnectorName) {
    htmlText += "&nbsp;&nbsp;<span class=\"custom_link_separator\">/</span>&nbsp;&nbsp;<a data-ga=\"['_trackEvent', 'CAM Posts Library', 'Download Connector Link', 'File: " + machine.machineConnectorName + "', 2, false]\" class=\"title download_link\" href='" + libraryUrl + "download-machine-connector.php?name=" + encodeURIComponent(machine.machineConnectorName) + "'>" + translate("Connector") + "</a>";
  }

  htmlText += "&nbsp;&nbsp;<span class=\"custom_link_separator\">/</span>&nbsp;&nbsp;<a class=\"title sample_link\" href='?m=" + encodeURIComponent(encodeMachineId(machine.filename)) + "' target='_blank'>" + translate("Share") + "</a>";

  if (!mobile && machine.editable) {
    htmlText += "&nbsp;&nbsp;<span class=\"custom_link_separator\">/</span>&nbsp;&nbsp;<a class=\"title sample_link\" href='/posteditor?url=" + encodeURIComponent(libraryUrl + "machines/" + machine.filename + ".json") + "' target='_blank'>" + translate("Open in Editor") + "</a>";
  }

  if (mobile) {
    htmlText += "</tr>";
  }

  return htmlText;
}

/** Add the machines table to the given element */
function addMachinesTableToElement(searchResults, element) {
  var html = "";
  var row = 0;
  var style = "border-collapse:collapse; width: 100%;";
  html += "<table border='0' align=\"left\" style='" + style + "'>";
  html += "<tbody>";
  var gotMore = false;
  for (var i in searchResults) {
    if (row >= 75) {
      gotMore = true;
      break;
    }
    var machine = searchResults[i];
    try {
      var image = getImageTag(machine);
      var title = "";
      if (machine.vendor) {
        title += machine.vendor
      }
      if (machine.model) {
        if (title.length) {
          title += " ";
        }
        title += machine.model;
      }
      if (!title.length) {
        title = machine.description
      }

      if (mobile) {
        html += getMachineHeadingSection(title, machine);
      }

      html += "<tr class=\"post\">";
      html += "<td class=\"postThumbnail\">" + image + "</td>";
      html += "<td class=\"info\"><table border='0' style='border-collapse:collapse'>";

      if (!mobile) {
        html += getMachineHeadingSection(title, machine);
      }

      html += "</td></tr>";

      if (machine.description && machine.description.toUpperCase() !== title.toUpperCase()) {
        html += "<tr class=\"minor\"><td colspan=\"3\">" + machine.description + "</td></tr>";
      } else if (machine.hidden) {
        html += "<tr class=\"minor attention\"><td colspan=\"3\">" + translate("ATTENTION") + ": " + translate("THIS MACHINE HAS NOT BEEN RELEASED, WONT WORK FOR ANY PARTICULAR PURPOSE, AND SHOULD NOT BE SHARED WITH THE COMMUNITY.") + "</td></tr>";
      }
      html += "<tr class=\"minor\"><td colspan=\"3\">" + translate("Purpose") + ": " + getTypeDescription(machine) + "</td></tr>";

      // Axis info
      if (machine.axis) {
        var tableAxis = [];
        var headAxis = [];
        for (i in machine.axis) {
          var axis = machine.axis[i];
          switch (axis.link) {
            case "table":
              tableAxis.push(axis.id);
              break;
            case "head":
              headAxis.push(axis.id);
              break;
          }
        }
        if (tableAxis.length > 0) {
          html += "<tr class=\"minor\"><td>" + translate("Table axis") + ": " + tableAxis.join(", ") + "</td></tr>";
        }
        if (headAxis.length > 0) {
          html += "<tr class=\"minor\"><td>" + translate("Head axis") + ": " + headAxis.join(", ") + "</td></tr>";
        }
      }
      if (machine.simulationModel) {
        html += "<tr class=\"minor\"><td colspan=\"3\">" + translate("Simulation ready") + ": " +  translate("Yes") + "</td></tr>";
      }

      html += "<tr class=\"minor\"><td colspan=\"3\">" + translate("Version") + ": " + machine.version + "</td></tr>";
      if (machine.dt) {
        html += "<tr class=\"minor\"><td colspan=\"3\">" + translate("Changed") + ": " + getSince(machine.dt) + "</td></tr>";
      }

      if (machine.count) {
        html += "<tr class=\"minor\"><td colspan=\"3\">" + translate("Downloads") + ": " + machine.count + "</td></tr>";
      }

      html += "</table></td>";
    } catch (e) {
    }
    row += 1;
  }

  if (gotMore) {
    html += "<tr><td colspan='2'>";
    html += translate("We have more machines available but we can't show them all here. Adjust your search criteria to find the right one for you.");
    html += "</td></tr>";
  }

  if (false && (row == 1) && machine && (previousSearchText.indexOf("machineid:") == 0)) {
    html += "<tr><td class=\"empty\" style=\"white-space: wrap;\"><a class=\"title sample_link\" href='/machines?search=vendor:" + machine.vendor + "'>" + translate("Look for machines for the same vendor") + "</a></td></tr>";
    html += "<tr><td class=\"empty\" colspan=\"2\" style=\"white-space: wrap;\"><a class=\"title sample_link\" href='/machines'>" + translate("Look for other machines") + "</a></td></tr>";
  }

  if (row == 0) {
    html += "<tr><td class=\"empty\" colspan=\"2\" style=\"white-space: wrap;\">" + translate("No machines matching your search criteria were found.") + "</td></tr>";

    if (filterType || filterAge || filterVendor) {
      html += "<tr><td class=\"empty\" colspan=\"2\" style=\"white-space: wrap;\"><a onclick=\"onResetSearch()\">" + translate("Reset search filter") + "</a></td></tr>";
    }

    html += "<tr><td class=\"empty\" colspan=\"2\" style=\"white-space: wrap;\"><ul><li>" + translate("Try to loosen your search criteria and find the closest matching generic machine. Our generic machines are designed to work with many different machine models and maybe also yours.") + "</li></br><li>" + translate("If you still cannot find what you are looking for you shouldn't stop here but instead ask our community at %1 for guidance.").replace("%1", "<a href=\"https://forums.autodesk.com/t5/hsm/ct-p/213\">forums.autodesk.com</a>") + "</li></br><li>" + translate("Keep in mind that providing good documentation is key for making a new machine. So spend some time collecting the required programming documentation and sample programs.").replace("%2", "<a href=\"https://forums.autodesk.com/t5/hsm-post-processor-forum/bd-p/218\">post processor forum</a>") + "</li></ul></td></tr>";
  }

  html += "</tbody>";
  html += "</table>";
  html += "</br>";

  element.innerHTML = html;
}

/** Update the list of machines based on the search criteria */
function updateSearchResult() {
  var searchElement = document.getElementById("search");
  if (!searchElement) {
    return;
  }

  var element = document.getElementById("result");
  if (!element) {
    return;
  }

  var searchText = cleanSearchText(searchElement.value);
  previousSearchText = searchText;

  if (searchText.toLowerCase() == "help") {
    addHelpTextToElement(element);
    return;
  }

  const searchCriteria = getSearchCriteriaFromText(searchText);

  if (machines.length == 0) {
    element.innerHTML = "<div>" + translate("No machines found.") + "<div>";
    return;
  }

  var searchResults = searchMachines(searchCriteria);
  searchResults.sort(sortByRating);

  readMoreTexts = [];
  changes = [];

  addMachinesTableToElement(searchResults, element);
}

function onRefresh() {
}

/** Reset search filter. */
function onResetSearch() {
  var searchElement = document.getElementById("search");
  searchElement.value = "";
  filterType = undefined;
  filterAge = undefined;
  filterVendor = undefined;
  filterSimulation = false;
  var element = document.getElementById("type");
  element.value = "ANY";
  element = document.getElementById("vendor");
  element.value = "";
  updateSearchResult();
}

var supportsJSON = false;
try {
  JSON;
  supportsJSON = true;
} catch (e) {
}

if (unsupportedInternetExplorer) {
  var element = document.getElementById('result');
  if (element) {
    element.innerHTML = "<pre>You need to use Firefox, Chrome, or Safari.</pre>";
  }
} else if (supportsJSON) {
  var refreshTime = 1000;
  window.setInterval(onRefresh, refreshTime);

  window.onload = function () {

    // disabled addLanguages();

    if (false) {
      var language = window.navigator.userLanguage || window.navigator.language;
      selectTranslation(language);

      var select = document.getElementById("selectLanguage");
      if (select) {
        var found = false;
        for (var i = 0; i < select.options.length; ++i) {
          if (select.options[i].value == language) {
            found = true;
            select.selectedIndex = i;
            break;
          }
        }
        if (!found) {
          var i = language.indexOf("-");
          if (i >= 0) {
            language = language.substr(0, i);
          }
          for (var i = 0; i < select.options.length; ++i) {
            if (select.options[i].value == language) {
              found = true;
              select.selectedIndex = i;
              break;
            }
          }
        }
      }
    }
    subscribeDownload();

    machines = loadMachines();
    posts = loadPosts();

    totalDownloads = 1;
    totalHits = 1;

    stats = loadStats();
    for (i in stats) {
      var s = stats[i];
      if (s.filename && s.count) {
        for (j in machines) {
          var p = machines[j];
          if (p.filename == s.filename) {
            p.count = s.count;
            totalDownloads += p.count;
            break;
          }
        }
      }
    }

    vendors = [];
    for (i in machines) {
      var p = machines[i];
      if (p.vendor && !p.hidden) {
        // console.log("VENDOR: " + p.vendor);
        if (vendors.indexOf(p.vendor) < 0) {
          vendors.push(p.vendor);
        }
      }
    }
    vendors.sort(function (a, b) { return a.toLowerCase().localeCompare(b.toLowerCase()); });

    var element = document.getElementById("vendor");
    if (element) {
      removeAllChildren(element);
      addOption(element, "", translate("Any vendor"));
      for (i in vendors) {
        var vendor = vendors[i];
        addOption(element, vendor, vendor);
      }
    }

    doSearch();
  };
} else {
  var element = document.getElementById('result');
  if (element) {
    element.innerHTML = "<pre>Browser does not support JSON.</pre>";
  }
}

