/** Route shell for /visualize — all the actual UI lives in VisualizeView. */
import VisualizeView from "../../components/VisualizeView";

export const metadata = { title: "Visualize" };

export default function VisualizePage() {
  return <VisualizeView />;
}
