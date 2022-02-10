import React, {FC, useState} from "react";
import {Link, useParams, useHistory} from "react-router-dom";
import {useAsync} from "react-use";
import {aironeApiClientV2} from "../apiclient/AironeApiClientV2";
import {AironeBreadcrumbs} from "../components/common/AironeBreadcrumbs";
import {Box, Container, IconButton, ListItemIcon, ListItemText, Menu, MenuItem, Paper, Typography} from "@mui/material";
import {
    aclPath,
    entitiesPath,
    entityEntriesPath,
    entryPath,
    topPath
} from "../Routes";
import {EntryDetails} from "../components/entry/EntryDetails";
import AppsIcon from "@mui/icons-material/Apps";
import {deleteEntry } from "../utils/AironeAPIClient";
import {Confirmable} from "../components/common/Confirmable";
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';

interface EntryControlProps {
    entryId: number;
    anchorElem: HTMLButtonElement | null;
    handleClose: (entryId: number) => void;
}

const EntryControlMenu: FC<EntryControlProps> = ({
                                                     entryId,
                                                     anchorElem,
                                                     handleClose,
                                                 }) => {
    const history = useHistory();

    const handleDelete = async (event, entryId) => {
        await deleteEntry(entryId);
        history.go(0);
    };

    return (
        <Paper sx={{width: 150}}>
            <Menu
                id={`entityControlMenu-${entryId}`}
                open={Boolean(anchorElem)}
                onClose={() => handleClose(entryId)}
                anchorEl={anchorElem}
            >
                <MenuItem component={Link} to={entryPath(entryId)}>
                    <Typography>編集</Typography>
                </MenuItem>
                <MenuItem>
                    <Typography>コピー</Typography>
                </MenuItem>
                <MenuItem component={Link} to={aclPath(entryId)}>
                    <Typography>ACL 設定</Typography>
                </MenuItem>
                <Confirmable
                    componentGenerator={(handleOpen) => (
                        <MenuItem onClick={handleOpen} sx={{justifyContent: "end"}}>
                            <ListItemText>削除</ListItemText>
                            <ListItemIcon>
                                <DeleteOutlineIcon />
                            </ListItemIcon>
                        </MenuItem>
                    )}
                    dialogTitle="本当に削除しますか？"
                    onClickYes={(e) => handleDelete(e, entryId)}
                />
            </Menu>
        </Paper>
    );
};

export const EntryDetailsPage: FC = () => {
    const {entryId} = useParams<{ entryId: number }>();

    const [entryAnchorEl, setEntryAnchorEl] =
        useState<HTMLButtonElement | null>();

    const entry: any = useAsync(async () => {
        return await aironeApiClientV2.getEntry(entryId);
    });

    return (
        <Box>
            <AironeBreadcrumbs>
                <Typography component={Link} to={topPath()}>
                    Top
                </Typography>
                <Typography component={Link} to={entitiesPath()}>
                    エンティティ一覧
                </Typography>
                {!entry.loading && (
                    <Typography
                        component={Link}
                        to={entityEntriesPath(entry.value.schema.id)}
                    >
                        {entry.value.schema.name}
                    </Typography>
                )}
                {!entry.loading && (
                    <Typography color="textPrimary">{entry.value.name}</Typography>
                )}
            </AironeBreadcrumbs>

            <Container maxWidth="lg" sx={{marginTop: "111px"}}>
                <Box display="flex">
                    <Box width="50px"/>
                    <Box flexGrow="1">
                        {!entry.loading && (
                            <Typography variant="h2" align="center">
                                {entry.value.name}
                            </Typography>
                        )}
                        <Typography variant="h4" align="center">
                            エントリ詳細
                        </Typography>
                    </Box>
                    <Box width="50px">
                        <IconButton
                            onClick={(e) => {
                                setEntryAnchorEl(e.currentTarget);
                            }}
                        >
                            <AppsIcon/>
                        </IconButton>
                        <EntryControlMenu
                            entryId={entryId}
                            anchorElem={entryAnchorEl}
                            handleClose={() => setEntryAnchorEl(null)}
                        />
                    </Box>
                </Box>

                {/* TODO */}
                <EntryDetails entry={entry.value}/>
            </Container>

        </Box>
    );
};
