import { useCallback, useEffect, useState } from "react";
import type { Repository } from "../../types/api";
import { getRepository } from "./api";

export function useRepository(repositoryId: string | undefined) {
  const [repository, setRepository] = useState<Repository | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!repositoryId) return;
    setLoading(true);
    setError(null);
    try {
      setRepository(await getRepository(repositoryId));
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, [repositoryId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { repository, error, loading, refresh, setRepository };
}
