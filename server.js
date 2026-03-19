<script type="module">
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getFirestore, collection, addDoc, getDocs } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyDi5JFBcQILI81DTknB8OtbgboDrMZdr7M",
  authDomain: "turkiye-ekolojik-katmanl-44c15.firebaseapp.com",
  projectId: "turkiye-ekolojik-katmanl-44c15",
  storageBucket: "turkiye-ekolojik-katmanl-44c15.firebasestorage.app",
  messagingSenderId: "590697215973",
  appId: "1:590697215973:web:20cd3d9addfe8c456fa10c"
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
