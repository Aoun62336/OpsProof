import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, LockKeyhole } from "lucide-react";

import { Brand } from "../components/Brand";
import { login } from "../lib/api";
import type { Session } from "../lib/types";

interface Props {
  onAuthenticated: (session: Session) => void;
}

export function LoginPage({
  onAuthenticated,
}: Props) {
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

    if (!accessKey.trim()) return;

    mutation.mutate(accessKey);
  }

  return (
    <div className="login-layout">
      <div className="login-panel">
        <Brand />

        <div className="login-panel__content">
          <div className="eyebrow">
            <LockKeyhole size={15} aria-hidden="true" />
            PRIVATE OPERATIONS WORKSPACE
          </div>

          <h1>
            Evidence over
            <span className="login-heading-accent">
              {" "}assumptions.
            </span>
          </h1>

          <p className="login-description">
            Investigate operational behavior, run controlled
            experiments and verify outcomes with recorded evidence.
          </p>

          <form className="login-form" onSubmit={submit}>
            <label htmlFor="access-key">
              Operator access key
            </label>

            <input
              id="access-key"
              type="password"
              autoComplete="off"
              value={accessKey}
              onChange={(event) =>
                setAccessKey(event.target.value)
              }
              required
              minLength={8}
              spellCheck={false}
            />

            <p className="field-help">
              Use your locally configured control-plane key.
              It is not stored in browser storage.
            </p>

            {mutation.isError && (
              <p className="inline-error" role="alert">
                Authentication failed. Check your access key
                and control-plane connection.
              </p>
            )}

            <button
              className="button button--primary"
              type="submit"
              disabled={mutation.isPending}
            >
              {mutation.isPending
                ? "Verifying access..."
                : "Enter workspace"}

              <ArrowRight size={17} aria-hidden="true" />
            </button>
          </form>
        </div>

        <div className="login-panel__footer">
          <span>OpsProof v0.2</span>
          <span>Controlled access · Local environment</span>
        </div>
      </div>

      <div className="login-aside" aria-hidden="true">
        <div className="login-aside__graphic">
          <div className="signal-line signal-line--one" />
          <div className="signal-line signal-line--two" />
          <div className="signal-line signal-line--three" />
        </div>

        <div className="login-aside__copy">
          <span className="eyebrow">
            CLOUD RELIABILITY VERIFICATION
          </span>

          <h2>Know what failed. Prove what recovered.</h2>

          <p>
            A disciplined workspace for operational evidence,
            safe decisions and reproducible reliability engineering.
          </p>
        </div>
      </div>
    </div>
  );
}
