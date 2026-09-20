const mocks = vi.hoisted(() => ({
  entryApiV2ImportCreate: vi.fn(),
  entryApiV2ImportPreviewCreate: vi.fn(),
}));

vi.mock("@dmm-com/airone-apiclient-typescript-fetch", () => {
  class EmptyApi {}

  class EntryApi {
    entryApiV2ImportCreate = mocks.entryApiV2ImportCreate;
    entryApiV2ImportPreviewCreate = mocks.entryApiV2ImportPreviewCreate;
  }

  return {
    Configuration: class Configuration {},
    AclApi: EmptyApi,
    CategoryApi: EmptyApi,
    EntityApi: EmptyApi,
    EntryApi,
    GroupApi: EmptyApi,
    JobApi: EmptyApi,
    RoleApi: EmptyApi,
    TriggerApi: EmptyApi,
    UserApi: EmptyApi,
  };
});

import { aironeApiClient } from "./AironeApiClient";

const requestBody = async (overrides: unknown): Promise<Blob> => {
  const init = overrides as RequestInit;
  if (!(init.body instanceof Blob)) {
    throw new Error("request body is not a Blob");
  }
  return init.body;
};

describe("AironeApiClient entry import", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("sends every approved preview job id to the entry import endpoint", async () => {
    mocks.entryApiV2ImportCreate.mockResolvedValue(undefined);

    await aironeApiClient.importEntries("entries: []", true, [42, 84]);

    expect(mocks.entryApiV2ImportCreate).toHaveBeenCalledWith(
      {
        entryImportEntity: [],
        force: true,
      },
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/yaml",
          "X-Pagoda-Preview-Job-Ids": "42,84",
          "X-CSRFToken": "",
        }),
      }),
    );
    const body = await requestBody(
      mocks.entryApiV2ImportCreate.mock.calls[0][1],
    );
    expect(body.type).toBe("");
    expect(await body.text()).toBe("entries: []");
  });

  test("returns every preview job id and backend validation error", async () => {
    mocks.entryApiV2ImportPreviewCreate.mockResolvedValue({
      result: {
        jobs: [{ jobId: 7 }, { jobId: 8 }],
        error: ["private: Entity is permission denied."],
      },
    });

    await expect(
      aironeApiClient.startImportEntriesPreview("entries: []"),
    ).resolves.toEqual({
      jobIds: [7, 8],
      errors: ["private: Entity is permission denied."],
    });
    expect(mocks.entryApiV2ImportPreviewCreate).toHaveBeenCalledWith(
      { entryImportEntity: [] },
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/yaml",
          "X-CSRFToken": "",
        }),
      }),
    );
    const body = await requestBody(
      mocks.entryApiV2ImportPreviewCreate.mock.calls[0][1],
    );
    expect(await body.text()).toBe("entries: []");
  });

  test("keeps a preview request failure observable by the caller", async () => {
    mocks.entryApiV2ImportPreviewCreate.mockRejectedValue(
      new Error("request failed"),
    );

    await expect(
      aironeApiClient.startImportEntriesPreview("entries: []"),
    ).rejects.toThrow("request failed");
  });
});
