/** Route shell for /ask — all the actual UI lives in AskView. */
import AskView from "../../components/AskView";

export const metadata = { title: "Ask" };

export default function AskPage() {
  return <AskView />;
}
