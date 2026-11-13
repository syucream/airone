import { useCallback, useMemo } from "react";
import { useNavigate, useLocation } from "react-router";

import { networkPath, topPath } from "../routes/Routes";

import { useError } from "./useError";

type Query = string | undefined;

export const useSimpleSearch = (): [
  Query,
  number,
  (query: Query) => void,
  (page: number) => void,
] => {
  const location = useLocation();
  const navigate = useNavigate();
  const raiseError = useError();
  const searchPath =
    location.pathname === networkPath() ? networkPath() : topPath();

  const query = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("simple_search_query") ?? undefined;
  }, [location.search]);

  const page = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const parsedPage = Number(params.get("simple_search_page") ?? "1");
    return Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  }, [location.search]);

  const submitQuery = useCallback(
    (query: Query) => {
      Promise.resolve(
        navigate({
          pathname: searchPath,
          search:
            query != null
              ? `simple_search_query=${encodeURIComponent(query)}&simple_search_page=1`
              : undefined,
        }),
      ).catch(raiseError);
    },
    [navigate, raiseError, searchPath],
  );

  const changePage = useCallback(
    (page: number) => {
      const params = new URLSearchParams(location.search);
      params.set("simple_search_page", page.toString());
      Promise.resolve(
        navigate({ pathname: searchPath, search: params.toString() }),
      ).catch(raiseError);
    },
    [location.search, navigate, raiseError, searchPath],
  );

  return [query, page, submitQuery, changePage];
};
