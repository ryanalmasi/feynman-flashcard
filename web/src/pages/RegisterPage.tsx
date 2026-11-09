import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { api, errorMessage } from "@/api/client";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const MIN_PASSWORD = 12;

export default function RegisterPage() {
  const { status, signedIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [month, setMonth] = useState("");
  const [year, setYear] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [passwordInvalid, setPasswordInvalid] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (status === "signed_in") return <Navigate to="/sets" replace />;

  const thisYear = new Date().getFullYear();
  const years = Array.from({ length: 101 }, (_, i) => thisYear - i);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setPasswordInvalid(false);
    if (!email || !password || !month || !year) {
      setError("Fill in all fields.");
      return;
    }
    if (password.length < MIN_PASSWORD) {
      setPasswordInvalid(true);
      return;
    }
    setSubmitting(true);
    try {
      const { data, error: err } = await api.POST("/auth/register", {
        body: {
          email,
          password,
          birth_month: Number(month),
          birth_year: Number(year),
        },
      });
      if (data) {
        signedIn(data);
        navigate("/sets", { replace: true });
      } else {
        setError(errorMessage(err));
      }
    } catch {
      setError(errorMessage(null));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm px-4 py-12">
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-semibold">Create your account</h1>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} noValidate className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                aria-describedby="password-hint"
                aria-invalid={passwordInvalid || undefined}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p
                id="password-hint"
                role={passwordInvalid ? "alert" : undefined}
                className={
                  passwordInvalid
                    ? "text-sm text-destructive"
                    : "text-sm text-muted-foreground"
                }
              >
                At least {MIN_PASSWORD} characters
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="birth-month">Birth month</Label>
                <NativeSelect
                  id="birth-month"
                  required
                  className="w-full"
                  value={month}
                  onChange={(e) => setMonth(e.target.value)}
                >
                  <NativeSelectOption value="">Month</NativeSelectOption>
                  {MONTHS.map((m, i) => (
                    <NativeSelectOption key={m} value={String(i + 1)}>
                      {m}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="birth-year">Birth year</Label>
                <NativeSelect
                  id="birth-year"
                  required
                  className="w-full"
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                >
                  <NativeSelectOption value="">Year</NativeSelectOption>
                  {years.map((y) => (
                    <NativeSelectOption key={y} value={String(y)}>
                      {y}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>
            </div>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" disabled={submitting}>
              Create account
            </Button>
          </form>
          <p className="mt-4 text-sm">
            <Link to="/login" className="underline">
              Already have an account? Log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
