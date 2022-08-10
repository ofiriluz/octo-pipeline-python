from octo_pipeline_python.common.database import Database
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class BackendsDatabase(Database):
    def __init__(self, context: WorkspaceContext):
        super().__init__(context.working_dir, context.name, f"{context.name}.backends")
