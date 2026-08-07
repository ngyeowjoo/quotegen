"""
Auth helpers: Supabase email/password auth + role/country lookups for RBAC.
"""
import streamlit as st
from app.supabase_client import get_client


def login_form():
    """Renders a login/signup form. Returns True if the user is authenticated."""
    if "sb_session" in st.session_state and st.session_state.sb_session:
        return True

    st.subheader("🔐 Sign in")
    tab_login, tab_signup = st.tabs(["Sign in", "Create account"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Sign in", type="primary"):
            try:
                res = get_client().auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.sb_session = res.session
                st.session_state.sb_user = res.user
                st.rerun()
            except Exception as e:
                st.error(f"Sign in failed: {e}")

    with tab_signup:
        st.caption("New accounts default to the 'Sales' role. An admin can upgrade your role afterward.")
        email2 = st.text_input("Email", key="signup_email")
        password2 = st.text_input("Password", type="password", key="signup_password")
        if st.button("Create account"):
            try:
                res = get_client().auth.sign_up({"email": email2, "password": password2})
                st.success("Account created. Check your email to confirm, then sign in.")
            except Exception as e:
                st.error(f"Sign up failed: {e}")

    return False


def logout():
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    for key in ("sb_session", "sb_user", "user_profile"):
        st.session_state.pop(key, None)
    st.rerun()


def current_user():
    return st.session_state.get("sb_user")


def current_profile():
    """Fetches (and caches in session) the user's role + profile row."""
    if "user_profile" in st.session_state:
        return st.session_state.user_profile
    user = current_user()
    if not user:
        return None
    res = get_client().table("user_profiles").select("*").eq("id", user.id).execute()
    profile = res.data[0] if res.data else None
    st.session_state.user_profile = profile
    return profile


def current_role():
    profile = current_profile()
    return profile["role"] if profile else None


def require_login():
    if not login_form():
        st.stop()


def require_role(*allowed_roles):
    require_login()
    role = current_role()
    if role not in allowed_roles:
        st.error(f"You don't have access to this page (requires: {', '.join(allowed_roles)}).")
        st.stop()
