import { createBrowserRouter, RouterProvider } from "react-router-dom";
import Home from "./pages/Home";
import ActivityCreate from './pages/ActivityCreate';
import Search from "./pages/ActivitySearch";
import ActivityView from "./pages/ActivityView";
import About from "./pages/About";
import Profile from "./pages/Profile";
import UserActivities from "./pages/UserActivities";
import Admin from "./pages/Admin";
import PendingUsers from "./pages/PendingUsers";
import PendingActivities from "./pages/PendingActivities";
import FileUploadTest from "./pages/FileUploadTest";
import FileUploadTest2 from "./pages/FileUploadTest2";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Splash from "./pages/Splash";
import { FeedbackProvider } from "./components/FeedbackContext/FeedbackContext";
import Layout from "./components/Layout/Layout";
  
const router = createBrowserRouter([
    {
        element: <Layout />,
        children: [
            /* User Routes */
            { path: "home", element: <Home />, handle: { title: "Welcome" } },
            { path: "create", element: <ActivityCreate />, handle: { title: "Activity Create" } },
            { path: "search", element: <Search />, handle: { title: "Activity Search" } },
            { path: "view/:activityId", element: <ActivityView />, handle: { title: "Activity View" } },
            { path: "about", element: <About />, handle: { title: "About" } },
            { path: "profile", element: <Profile />, handle: { title: "Profile" } },
            { path: "myactivities", element: <UserActivities />, handle: { title: "My Activities" } },

            /* Admin Routes */
            { path: "admin", element: <Admin />, handle: { title: "Admin" } },
            { path: "pendingUsers", element: <PendingUsers />, handle: { title: "Pending Users" } },
            { path: "pendingActivities", element: <PendingActivities />, handle: { title: "Pending Activities" } },

            /* Testing Routes */
            { path: "fileUploadTest", element: <FileUploadTest />, handle: { title: "File Upload Test" } },
            { path: "fileUploadTest2", element: <FileUploadTest2 />, handle: { title: "File Upload Test 2" } },
        ],
    },
    /* Auth Routes */
    { path: "login", element: <Login /> },
    { path: "register", element: <Register /> },

    /* Default Route */
    { path: "", element: <Splash /> }
]);

function App() {
    return (
        <FeedbackProvider>
            <RouterProvider router={router} />
        </FeedbackProvider>
    );
}

export default App;
  