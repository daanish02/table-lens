import RawDataBrowser from "../../../../components/RawDataBrowser";

export default function BrowseTablePage({ params }: { params: { table: string } }) {
  return <RawDataBrowser table={params.table} />;
}
