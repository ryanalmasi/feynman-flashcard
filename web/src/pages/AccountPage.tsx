import { startTransition, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { api, errorMessage } from "@/api/client";
import { useAuth } from "@/auth/useAuth";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

export default function AccountPage() {
  const { user, signedOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // React Router navigates in a transition; clear auth in the same transition so
  // RequireAuth never renders "signed out" on /account and adds its own ?next=.
  function leave(to: string) {
    startTransition(() => {
      navigate(to, { replace: true });
      signedOut();
    });
  }

  async function logout() {
    try {
      await api.POST("/auth/logout");
    } catch {
      // Network failure: still clear local state; the cookie expires server-side.
    }
    leave("/login");
  }

  async function onDelete(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setDeleting(true);
    try {
      const { response, error: err } = await api.DELETE("/auth/account", {
        body: { password },
      });
      if (response.status === 204) {
        leave("/register");
        toast.success("Your account has been deleted.");
      } else {
        setError(errorMessage(err));
      }
    } catch {
      setError(errorMessage(null));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="grid max-w-xl gap-6">
      <h1 className="text-2xl font-semibold">Account</h1>
      <div>
        <p className="text-sm text-muted-foreground">Email</p>
        <p>{user?.email}</p>
      </div>
      <div>
        <Button variant="outline" onClick={logout}>
          Log out
        </Button>
      </div>
      <Separator />
      <section className="grid gap-3 rounded-lg border border-destructive p-4">
        <h2 className="text-lg font-semibold text-destructive">Danger zone</h2>
        <div>
          <AlertDialog
            open={open}
            onOpenChange={(o) => {
              setOpen(o);
              if (!o) {
                setPassword("");
                setError(null);
              }
            }}
          >
            <AlertDialogTrigger asChild>
              <Button variant="destructive">Delete account</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <form onSubmit={onDelete} className="grid gap-4">
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete your account?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This permanently deletes your account, all your study sets,
                    cards and uploaded PDFs. This can't be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <div className="grid gap-2">
                  <Label htmlFor="delete-password">Password</Label>
                  <Input
                    id="delete-password"
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
                {error && (
                  <p role="alert" className="text-sm text-destructive">
                    {error}
                  </p>
                )}
                <AlertDialogFooter>
                  <AlertDialogCancel type="button">Cancel</AlertDialogCancel>
                  <Button
                    type="submit"
                    variant="destructive"
                    disabled={deleting}
                  >
                    Delete my account
                  </Button>
                </AlertDialogFooter>
              </form>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </section>
    </div>
  );
}
