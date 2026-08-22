import TableDetail from "../../../../components/TableDetail";

export default function BrowseTablePage({ params }: { params: { table: string } }) {
  return <TableDetail table={params.table} />;
}
