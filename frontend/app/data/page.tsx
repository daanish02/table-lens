/** Route shell for /data — all the actual UI lives in DataOverview. */
import DataOverview from "../../components/DataOverview";

export const metadata = { title: "Data" };

export default function DataPage() {
  return <DataOverview />;
}
