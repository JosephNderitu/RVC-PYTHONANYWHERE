importScripts("https://www.gstatic.com/firebasejs/8.2.1/firebase-app.js");
importScripts("https://www.gstatic.com/firebasejs/8.2.1/firebase-messaging.js");

const firebaseConfig = {
    apiKey: "AIzaSyCl3ncPk3XOmn-pT-5Xet9UFYxEMz--jVE",
    authDomain: "riftvalley-carriers-project.firebaseapp.com",
    projectId: "riftvalley-carriers-project",
    storageBucket: "riftvalley-carriers-project.appspot.com",
    messagingSenderId: "277861847457",
    appId: "1:277861847457:web:83a1643b691da99160fbe0",
    measurementId: "G-R2JC67RFG6"
  };


if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
}

const messaging = firebase.messaging();
