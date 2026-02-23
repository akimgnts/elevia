import React from "react";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo });
    console.error("[ErrorBoundary] Caught:", error, errorInfo);
  }

  private handleCopyStack = () => {
    const text = [
      this.state.error?.toString() ?? "",
      this.state.errorInfo?.componentStack ?? "",
    ].join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  };

  private handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.href = "/analyze";
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-md rounded-2xl border border-red-100 bg-white p-8 shadow-sm">
          <div className="mb-4 text-3xl">⚠️</div>
          <h2 className="text-lg font-bold text-slate-900">Une erreur inattendue s'est produite</h2>
          <p className="mt-2 text-sm text-slate-500">
            Revenez à la page d'analyse pour réessayer. Si le problème persiste, copiez la trace
            ci-dessous et signalez-la.
          </p>

          {this.state.error && (
            <pre className="mt-4 max-h-32 overflow-auto rounded-xl bg-slate-50 p-3 text-xs text-slate-600">
              {this.state.error.toString()}
            </pre>
          )}

          <div className="mt-6 flex gap-3">
            <button
              onClick={this.handleReset}
              className="flex-1 rounded-xl bg-cyan-500 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-600"
            >
              Retour à l'analyse
            </button>
            <button
              onClick={this.handleCopyStack}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              Copier la trace
            </button>
          </div>
        </div>
      </div>
    );
  }
}
