import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { routerPaths } from "src/app/routerPaths";
import authStateService from "src/auth/services/AuthenticationState.service";

interface AdminRouteProps {
  children: ReactNode;
}

/**
 * Guards staff-only routes (admin panel + report downloads). The visitor must be logged in
 * AND hold the Firebase `super_admin` claim. Logged-out visitors are sent to the landing page;
 * logged-in non-admins are sent to the chat. Replaces the old `?token=` query-string gate.
 */
const AdminRoute: React.FC<AdminRouteProps> = ({ children }) => {
  const user = authStateService.getInstance().getUser();
  if (!user) {
    return <Navigate to={routerPaths.LANDING} />;
  }
  if (!authStateService.getInstance().getIsSuperAdmin()) {
    return <Navigate to={routerPaths.ROOT} />;
  }
  return <>{children}</>;
};

export default AdminRoute;
