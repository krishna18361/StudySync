import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { isLoggedIn } from "./api";
import Auth from "./pages/Auth.jsx";
import Workspace from "./pages/Workspace.jsx";

function Private({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />;
}

/** Fades and lifts each route into view on navigation. */
function PageTransition({ children }) {
  const location = useLocation();
  return (
    <div className="page-transition" key={location.pathname}>
      {children}
    </div>
  );
}

export default function App() {
  return (
    <PageTransition>
      <Routes>
        <Route path="/login" element={<Auth mode="login" />} />
        <Route path="/register" element={<Auth mode="register" />} />
        <Route
          path="/"
          element={
            <Private>
              <Workspace />
            </Private>
          }
        />
      </Routes>
    </PageTransition>
  );
}
