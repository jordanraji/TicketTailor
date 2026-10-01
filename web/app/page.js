import { notFound } from "next/navigation";
import { redirect } from "next/navigation";

export default function Page() {
  // const user = null;

  // if (!user) {
  //   notFound();
  // }

  // return <div>User Found</div>;

  redirect("/home");
}
