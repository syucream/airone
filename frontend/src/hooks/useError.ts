import { useCallback, useState } from "react";

export function useError(): (error: unknown) => void {
  const [, setState] = useState();
  return useCallback((error: unknown) => {
    setState(() => {
      throw error;
    });
  }, []);
}
