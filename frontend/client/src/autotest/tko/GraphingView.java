package autotest.tko;

import autotest.common.CustomHistory.HistoryToken;
import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.TabView;
import autotest.tko.TableView.TableSwitchListener;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.user.client.ui.DeckPanel;

import java.util.Map;

public class GraphingView extends TabView {

    private ExtendedListBox frontendSelection = new ExtendedListBox();
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
        super.initialize();
        frontendSelection.addItem("Metrics Plot", metricsPlotFrontend.getFrontendId());
        frontendSelection.addItem("Machine Qualification Histogram", 
                                  machineQualHistogramFrontend.getFrontendId());
        frontendSelection.addItem("Existing Graphs", existingGraphsFrontend.getFrontendId());

        frontendSelection.addChangeHandler(new ChangeHandler() {
            public void onChange(ChangeEvent event) {
                showSelectedView();
                updateHistory();
            }
        });

        controlPanel.add(metricsPlotFrontend);
        controlPanel.add(machineQualHistogramFrontend);
        controlPanel.add(existingGraphsFrontend);
        controlPanel.showWidget(0);

        addWidget(frontendSelection, "graphing_type");
        addWidget(controlPanel, "graphing_frontend");
    }

    @Override
    public String getElementId() {
        return "graphing_view";
    }
    
    private GraphingFrontend getSelectedFrontend() {
        return frontends[frontendSelection.getSelectedIndex()];
    }

    @Override
    public void refresh() {
        super.refresh();
        getSelectedFrontend().refresh();
    }

    @Override
    public void display() {
        super.display();
        CommonPanel.getPanel().setConditionVisible(false);
    }
    
    @Override
    public HistoryToken getHistoryArguments() {
        HistoryToken args = super.getHistoryArguments();
        args.put("view", getSelectedFrontend().getFrontendId());
        getSelectedFrontend().addToHistory(args);
        return args;
    }

    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        super.handleHistoryArguments(arguments);
        String frontendId = arguments.get("view");
        frontendSelection.selectByValue(frontendId);
        for (GraphingFrontend frontend : frontends) {
            if (frontend.getFrontendId().equals(frontendId)) {
                frontend.handleHistoryArguments(arguments);
                break;
            }
        }
        showSelectedView();
    }
    
    private void showSelectedView() {
        int index = frontendSelection.getSelectedIndex();
        controlPanel.showWidget(index);
        frontends[index].refresh();
    }
}
