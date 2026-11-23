"use client";

import { useEffect, useState } from "react";

import { getSignedIn, SIGN_IN_URL, type SignedIn, signOut } from "@/api";

import StartPicker from "./StartPicker";

type State = { kind: "checking" } | { kind: "signed_out" } | { kind: "signed_in"; owner: SignedIn }
  | { kind: "unreachable" };

// Only Tom's GitHub account gets a session. Checking it also wakes a sleeping API early.
export default function SignIn() {
  const [state, setState] = useState<State>({ kind: "checking" });

  useEffect(() => {
    getSignedIn()
      .then((owner) => setState(owner ? { kind: "signed_in", owner } : { kind: "signed_out" }))
      .catch(() => setState({ kind: "unreachable" }));
  }, []);

  if (state.kind === "checking") {
    return <p role="status">Checking sign-in… (the API can take a minute to wake up)</p>;
  }
  if (state.kind === "unreachable") {
    return <p role="alert">The route API could not be reached. Reload to try again.</p>;
  }
  if (state.kind === "signed_out") {
    return (
      <a className="sign-in" href={SIGN_IN_URL}>
        Sign in with GitHub
      </a>
    );
  }
  return (
    <>
      <StartPicker />
      <button
        type="button"
        className="sign-out"
        onClick={() => signOut().then(() => setState({ kind: "signed_out" }))}
      >
        Sign out
      </button>
    </>
  );
}
