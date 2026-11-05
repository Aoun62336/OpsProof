import {
  useState,
  type FormEvent,
} from "react";

import { useMutation } from "@tanstack/react-query";
import { ArrowRight, LockKeyhole } from "lucide-react";

import { Brand } from "../components/Brand";
import { login } from "../lib/api";
import type { Session } from "../lib/types";

export function LoginPage({
  onAuthenticated,
}: {
  onAuthenticated: (session: Session) => void;
}) {
  const [accessKey, setAccessKey] = useState("");

  const mutation = useMutation({
    mutationFn: login,

    onSuccess: (session) => {
      setAccessKey("");
      onAuthenticated(session);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (accessKey.trim()) {
      mutation.mutate(accessKey);
    }
  }

  return (
    <div className="login-layout">
      <section
        className="login-story"
        aria-label="About OpsProof"
      >
        <Brand />

        <div className="login-story__main">
          <p className="overline overline--light">
            CLOUD RELIABILITY & SAFE OPERATIONS
          </p>

          <h1>
            Every recovery <em>deserves proof.</em>
          </h1>

          <p>
            Investigate failures, run controlled operations
            and verify outcomes against recorded evidence.
          </p>

          <div
            className="login-principles"
            aria-label="Platform approach"
          >
            <span>
              01 <strong>Observe</strong>
            </span>
            <span>
              02 <strong>Act</strong>
            </span>
            <span>
              03 <strong>Verify</strong>
            </span>
          </div>
        </div>

        <p className="login-story__footer">
          OpsProof / Engineering workspace / v0.2
        </p>
      </section>

      <section
        className="login-access"
        aria-labelledby="login-title"
      >
        <div className="login-access__card">
          <div className="login-access__mark">
            <LockKeyhole
              size={21}
              aria-hidden="true"
            />
          </div>

          <p className="overline">OPERATOR ACCESS</p>

          <h2 id="login-title">
            Enter your workspace
          </h2>

          <p className="login-access__intro">
            Private access to the local control plane.
            Your management key is never stored in browser
            storage.
          </p>

          <form
            onSubmit={submit}
            className="login-form"
          >
            <label htmlFor="access-key">
              Operator access key
            </label>

            <input
              id="access-key"
              type="password"
              autoComplete="off"
              minLength={8}
              required
              spellCheck={false}
              value={accessKey}
              onChange={(event) =>
                setAccessKey(event.target.value)
              }
            />

            {mutation.isError && (
              <p className="inline-error" role="alert">
                Could not authenticate. Check your key
                and connection.
              </p>
            )}

            <button
              className="button button--primary"
              type="submit"
              disabled={mutation.isPending}
            >
              {mutation.isPending
                ? "Verifying access…"
                : "Enter workspace"}

              <ArrowRight
                size={17}
                aria-hidden="true"
              />
            </button>
          </form>

          <p className="login-access__hint">
            Local environment · Session expires after 8 hours
          </p>
        </div>
      </section>
    </div>
  );
}
