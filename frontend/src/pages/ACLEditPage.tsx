import {
  ACLObjtypeEnum,
  EntityDetail,
  EntryRetrieve,
} from "@dmm-com/airone-apiclient-typescript-fetch";
import { zodResolver } from "@hookform/resolvers/zod";
import { Box, Container, Typography } from "@mui/material";
import { useSnackbar } from "notistack";
import { FC, Suspense, useCallback, useEffect, useState } from "react";
import { FieldErrors, useForm } from "react-hook-form";
import { useNavigate } from "react-router";

import { usePagodaSWR } from "../hooks/usePagodaSWR";

import { AironeBreadcrumbs, AironeLink } from "components";
import { ACLForm } from "components/acl/ACLForm";
import { Schema, schema } from "components/acl/aclForm/ACLFormSchema";
import { Loading } from "components/common/Loading";
import { PageHeader } from "components/common/PageHeader";
import { SubmitButton } from "components/common/SubmitButton";
import { EntityBreadcrumbs } from "components/entity/EntityBreadcrumbs";
import { EntryBreadcrumbs } from "components/entry/EntryBreadcrumbs";
import { usePrompt } from "hooks/usePrompt";
import { useTranslation } from "hooks/useTranslation";
import { useTypedParams } from "hooks/useTypedParams";
import { translate } from "i18n/config";
import { aironeApiClient } from "repository/AironeApiClient";
import {
  editEntityPath,
  entityEntriesPath,
  entryDetailsPath,
  listCategoryPath,
  topPath,
} from "routes/Routes";

const ACLEditContent: FC<{ objectId: number }> = ({ objectId }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const [entity, setEntity] = useState<EntityDetail>();
  const [entry, setEntry] = useState<EntryRetrieve>();
  const [breadcrumbs, setBreadcrumbs] = useState<JSX.Element>(<Box />);

  const {
    formState: { isDirty, isSubmitting, isSubmitSuccessful },
    handleSubmit,
    reset,
    control,
    watch,
  } = useForm<Schema>({
    resolver: zodResolver(schema),
    mode: "onSubmit",
  });

  usePrompt(isDirty && !isSubmitSuccessful, t("acl.form.confirmLeave"));

  const { data: acl } = usePagodaSWR(
    ["acl", objectId],
    () => aironeApiClient.getAcl(objectId),
    { suspense: true },
  );

  const historyReplace = () => {
    switch (acl.objtype) {
      case ACLObjtypeEnum.Category:
        navigate(listCategoryPath(), { replace: true });
        break;
      case ACLObjtypeEnum.Entity:
        if (entity?.id) {
          navigate(entityEntriesPath(entity?.id), { replace: true });
        }
        break;
      case ACLObjtypeEnum.EntityAttr:
        if (entity?.id) {
          navigate(editEntityPath(entity?.id), { replace: true });
        }
        break;
      case ACLObjtypeEnum.Entry:
        if (entry?.id) {
          navigate(entryDetailsPath(entry?.schema.id, entry?.id), {
            replace: true,
          });
        }
        break;
    }
  };

  const handleSubmitOnInvalid = useCallback(
    async (err: FieldErrors<Schema & { generalError: string }>) => {
      err.generalError &&
        enqueueSnackbar(err.generalError.message, { variant: "error" });
    },
    [enqueueSnackbar],
  );

  const handleSubmitOnValid = useCallback(
    async (aclForm: Schema) => {
      const aclSettings =
        aclForm.roles.map((role) => ({
          memberId: role.id,
          value: role.currentPermission,
        })) ?? [];

      await aironeApiClient.updateAcl(
        objectId,
        aclForm.isPublic,
        aclSettings,
        aclForm.objtype,
        aclForm.defaultPermission,
      );

      enqueueSnackbar(translate("acl.form.updateSuccess"), {
        variant: "success",
      });
    },
    [objectId, enqueueSnackbar],
  );

  const handleCancel = async () => {
    historyReplace();
  };

  /* initialize permissions and isPublic variables from acl parameter */
  useEffect(() => {
    reset({
      isPublic: acl.isPublic,
      defaultPermission: acl.defaultPermission,
      objtype: acl.objtype,
      roles: acl.roles,
    });
    switch (acl.objtype) {
      case ACLObjtypeEnum.Category:
        setBreadcrumbs(
          <AironeBreadcrumbs>
            <Typography component={AironeLink} to={topPath()}>
              Top
            </Typography>
            <Typography component={AironeLink} to={listCategoryPath()}>
              {translate("acl.breadcrumb.categoryList")}
            </Typography>
            <Typography color="textPrimary">{acl.name}</Typography>
            <Typography color="textPrimary">
              {translate("acl.page.title")}
            </Typography>
          </AironeBreadcrumbs>,
        );
        break;
      case ACLObjtypeEnum.Entity:
        aironeApiClient.getEntity(objectId).then((resp) => {
          setEntity(resp);
          setBreadcrumbs(
            <EntityBreadcrumbs
              entity={resp}
              title={translate("acl.page.title")}
            />,
          );
        });
        break;
      case ACLObjtypeEnum.EntityAttr:
        if (acl.parent?.id) {
          aironeApiClient.getEntity(acl.parent?.id).then((resp) => {
            setEntity(resp);
            setBreadcrumbs(
              <EntityBreadcrumbs
                entity={resp}
                attr={acl.name}
                title={translate("acl.page.title")}
              />,
            );
          });
        }

        break;
      case ACLObjtypeEnum.Entry:
        aironeApiClient.getEntry(objectId).then((resp) => {
          setEntry(resp);
          setBreadcrumbs(
            <EntryBreadcrumbs
              entry={resp}
              title={translate("acl.page.title")}
            />,
          );
        });
        break;
    }
  }, [acl, reset, objectId]);

  useEffect(() => {
    if (isSubmitSuccessful) {
      historyReplace();
    }
  }, [isSubmitSuccessful]);

  return (
    <>
      {breadcrumbs}

      <PageHeader title={acl.name} description={t("acl.page.title")}>
        <SubmitButton
          name={t("common.save")}
          disabled={isSubmitting || isSubmitSuccessful}
          isSubmitting={isSubmitting}
          handleSubmit={handleSubmit(
            handleSubmitOnValid,
            handleSubmitOnInvalid,
          )}
          handleCancel={handleCancel}
        />
      </PageHeader>

      {isSubmitting ? (
        <Loading />
      ) : (
        <Container>
          <ACLForm control={control} watch={watch} />
        </Container>
      )}
    </>
  );
};

export const ACLEditPage: FC = () => {
  const { objectId } = useTypedParams<{ objectId: number }>();

  return (
    <Box className="container-fluid">
      <Suspense fallback={<Loading />}>
        <ACLEditContent objectId={objectId} />
      </Suspense>
    </Box>
  );
};
