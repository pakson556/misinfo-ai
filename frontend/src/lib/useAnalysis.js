/*
 * useAnalysis(): the "brain" of the Check page.
 *
 * A custom React hook that holds everything about the current check (claims,
 * verdicts so far, tactics, final result...) and updates it as events stream in
 * from the backend. The page components just read this state and draw it.
 *
 *   run(input)  start a new check (cancels any running one)
 *   load(result) show a saved check (used by the Report page)
 *   reset()     go back to the empty input box
 *
 * Event names match the ones yielded by backend/app/pipeline/orchestrator.py.
 */
import { useCallback, useRef, useState } from "react";
import { api } from "./api.js";

const EMPTY = {
  status: "idle", // idle | running | done | error
  error: "",
  text: "",
  stages: {},
  claims: [], // Claim objects
  results: {}, // claim id -> ClaimResult
  tactics: [],
  tacticsScore: 0,
  style: null,
  result: null,
};

export function useAnalysis() {
  const [state, setState] = useState(EMPTY);
  // AbortController lets us cancel a running check (Stop button / starting a new one).
  const ctrl = useRef(null);

  const run = useCallback(async (input) => {
    ctrl.current?.abort();
    const controller = new AbortController();
    ctrl.current = controller;
    setState({ ...EMPTY, status: "running", text: input.text || "" });

    // Called once per event from the backend. Each case updates one part of the
    // state; React then redraws only what changed (e.g. one claim turning red).
    const onEvent = (name, data) => {
      setState((s) => {
        switch (name) {
          case "input":
            return { ...s, text: data.text };
          case "stage":
            return { ...s, stages: { ...s.stages, [data.stage]: data } };
          case "claims":
            return { ...s, claims: data.claims };
          case "tactics":
            return { ...s, tactics: data.tactics, tacticsScore: data.score };
          case "style":
            return { ...s, style: data };
          case "claim_result":
            return { ...s, results: { ...s.results, [data.claim.id]: data } };
          case "result":
            return {
              ...s,
              status: "done",
              result: data,
              // image / URL inputs: the analysed text only becomes known on the server
              text: data.input_text || s.text || data.input_preview,
            };
          case "error":
            return { ...s, status: "error", error: data.message };
          default:
            return s;
        }
      });
    };

    try {
      await api.analyzeStream(input, onEvent, controller.signal);
      setState((s) => (s.status === "running" ? { ...s, status: "error", error: "The connection closed before the check finished. Try again." } : s));
    } catch (e) {
      if (controller.signal.aborted) return;
      setState((s) => ({ ...s, status: "error", error: e.message }));
    }
  }, []);

  const load = useCallback((result) => {
    const results = Object.fromEntries(result.claims.map((c) => [c.claim.id, c]));
    setState({
      ...EMPTY,
      status: "done",
      text: result.input_text || result.input_preview,
      claims: result.claims.map((c) => c.claim),
      results,
      tactics: result.tactics,
      tacticsScore: result.tactics_score,
      style: result.style,
      result,
    });
  }, []);

  const reset = useCallback(() => {
    ctrl.current?.abort();
    setState(EMPTY);
  }, []);

  return { ...state, run, load, reset };
}
