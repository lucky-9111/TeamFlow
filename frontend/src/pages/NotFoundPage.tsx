import { SearchX } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/States";

export function NotFoundPage({ what = "page" }: { what?: string }) {
  return (
    <div className="card">
      <EmptyState
        icon={SearchX}
        title={`This ${what} doesn't exist`}
        description={`It may have been deleted, or you may not have access to it.`}
        action={
          <Link to="/">
            <Button size="sm">Go to Overview</Button>
          </Link>
        }
      />
    </div>
  );
}
