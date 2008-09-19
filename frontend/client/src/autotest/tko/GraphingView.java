package autotest.tko;

import autotest.common.ui.TabView;
import autotest.tko.TableView.TableSwitchListener;

import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.DeckPanel;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.Map;

public class GraphingView extends TabView {

    private ListBox frontendSelection = new ListBox();
    private MetricsPlotFrontend metricsPlotFrontend = new MetricsPlotFrontend(this);
    private MachineQualHistogramFrontend machineQualHistogramFrontend =
        new MachineQualHistogramFrontend(this);
    private ExistingGraphsFrontend existingGraphsFrontend = new ExistingGraphsFrontend(this);
    private DeckPanel controlPanel = new DeckPanel();
    private GraphingFrontend frontends[] = {
            metricsPlotFrontend,
            machineQualHistogramFrontend,
            existingGraphsFrontend,
    };

    public GraphingView(TableSwitchListener listener) {
        metricsPlotFrontend.setListener(listener);
        machineQualHistogramFrontend.setListener(listener);
    }
    
    @Override
    public void initialize() {
        frontendSelection.addItem("Metrics Plot");
        frontendSelection.addItem("Machine Qualification Histogram");
        frontendSelection.addItem("Existing Graphs");

        frontendSelection.addChangeListener(new ChangeListener() {
            public void onChange(Widget w) {
                showSelectedView();
                updateHistory();
            }
        });

        controlPanel.add(metricsPlotFrontend);
        controlPanel.add(machineQualHistogramFrontend);
        controlPanel.add(existingGraphsFrontend);
        controlPanel.showWidget(0);

        RootPanel.get("graphing_type").add(frontendSelection);
        RootPanel.get("graphing_frontend").add(controlPanel);
    }

    @Override
    public String getElementId() {
        return "graphing_view";
    }

    @Override
    public void refresh() {
        super.refresh();
        frontends[frontendSelection.getSelectedIndex()].refresh();
    }

    @Override
    public void display() {
        super.display();
        CommonPanel.getPanel().setConditionVisible(false);
    }
    
    @Override
    protected Map<String, String> getHistoryArguments() {
        Map<String, String> args = super.getHistoryArguments();
        args.put("view", frontendSelection.getValue(frontendSelection.getSelectedIndex()));
        frontends[frontendSelection.getSelectedIndex()].addToHistory(args);
        return args;
    }

    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        super.handleHistoryArguments(arguments);
        for (int i = 0; i < frontendSelection.getItemCount(); i++) {
            if (frontendSelection.getValue(i).equals(arguments.get("view"))) {
                frontendSelection.setSelectedIndex(i);
                frontends[i].handleHistoryArguments(arguments);
                showSelectedView();
                break;
            }
        }
    }
    
    private void showSelectedView() {
        int index = frontendSelection.getSelectedIndex();
        controlPanel.showWidget(index);
        frontends[index].refresh();
    }
}
