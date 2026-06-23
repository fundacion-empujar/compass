// mute the console
import "src/_test_utilities/consoleMock";

import React from "react";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import AdminRoute from "./AdminRoute";
import { routerPaths } from "src/app/routerPaths";
import authStateService from "src/auth/services/AuthenticationState.service";
import { resetAllMethodMocks } from "src/_test_utilities/resetAllMethodMocks";
import { TabiyaUser } from "src/auth/auth.types";

const setAuth = (loggedIn: boolean, isSuperAdmin: boolean) => {
  jest
    .spyOn(authStateService.getInstance(), "getUser")
    .mockReturnValue(loggedIn ? ({ id: "user1" } as TabiyaUser) : null);
  jest.spyOn(authStateService.getInstance(), "getIsSuperAdmin").mockReturnValue(isSuperAdmin);
};

const renderAdminRoute = () => {
  const router = createMemoryRouter(
    [
      {
        path: routerPaths.ADMIN_PANEL,
        element: (
          <AdminRoute>
            <div>Admin Panel</div>
          </AdminRoute>
        ),
      },
      { path: routerPaths.ROOT, element: <div>Chat Page</div> },
      { path: routerPaths.LANDING, element: <div>Landing Page</div> },
    ],
    { initialEntries: [routerPaths.ADMIN_PANEL] }
  );
  render(<RouterProvider router={router} />);
};

describe("AdminRoute", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetAllMethodMocks(authStateService.getInstance());
  });

  test("renders the admin page for a logged-in super-admin", () => {
    // GIVEN a logged-in user holding the super_admin claim
    setAuth(true, true);
    // WHEN the admin route renders
    renderAdminRoute();
    // THEN the guarded page is shown
    expect(screen.getByText("Admin Panel")).toBeInTheDocument();
    expect(console.error).not.toHaveBeenCalled();
  });

  test("redirects a logged-in non-admin to the chat", () => {
    // GIVEN a logged-in user WITHOUT the super_admin claim
    setAuth(true, false);
    // WHEN the admin route renders
    renderAdminRoute();
    // THEN they are sent to the chat, not the panel
    expect(screen.getByText("Chat Page")).toBeInTheDocument();
    expect(screen.queryByText("Admin Panel")).not.toBeInTheDocument();
  });

  test("redirects a logged-out visitor to the landing page", () => {
    // GIVEN no logged-in user
    setAuth(false, false);
    // WHEN the admin route renders
    renderAdminRoute();
    // THEN they are sent to the landing page
    expect(screen.getByText("Landing Page")).toBeInTheDocument();
    expect(screen.queryByText("Admin Panel")).not.toBeInTheDocument();
  });
});
