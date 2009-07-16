package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.ui.TabView;
import autotest.tko.PreconfigSelector.PreconfigHandler;
import autotest.tko.TableView.TableSwitchListener;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.HasHorizontalAlignment;
import com.google.gwt.user.client.ui.Widget;

import java.util.Map;

public abstract class DynamicGraphingFrontend extends GraphingFrontend 
                                              implements ClickListener, PreconfigHandler {
    protected PreconfigSelector preconfig;
    protected Button graphButton = new Button("Graph");
    protected Plot plot;
    private TabView parent;

    public DynamicGraphingFrontend(final TabView parent, Plot plot, String preconfigType) {
        this.parent = parent;
        this.plot = plot;
        plot.setDrilldownTrigger();
        preconfig = new PreconfigSelector(preconfigType, this);
        graphButton.addClickListener(this);
    }

    @Override
    public void onClick(Widget sender) {
        if (sender != graphButton) {
            super.onClick(sender);
            return;
        }
        
        parent.updateHistory();
        plot.setVisible(false);
        embeddingLink.setVisible(false);
        graphButton.setEnabled(false);
        
        JSONObject params = buildParams();
        if (params == null) {
            graphButton.setEnabled(true);
            return;
        }
        
        plot.refresh(params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                plot.setVisible(true);
                embeddingLink.setVisible(true);
                graphButton.setEnabled(true);
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                graphButton.setEnabled(true);
            }
        });
    }

    protected abstract JSONObject buildParams();

    @Override
    public void refresh() {
        // Nothing to refresh
    }

    protected void commonInitialization() {
        table.setWidget(table.getRowCount(), 1, graphButton);
        table.setWidget(table.getRowCount(), 0, plot);
        table.getFlexCellFormatter().setColSpan(table.getRowCount() - 1, 0, 3);
        
        table.setWidget(table.getRowCount(), 2, embeddingLink);
        table.getFlexCellFormatter().setHorizontalAlignment(
                table.getRowCount() - 1, 2, HasHorizontalAlignment.ALIGN_RIGHT);
        
        plot.setVisible(false);
        embeddingLink.setVisible(false);
        
        initWidget(table);
    }

    public void handlePreconfig(Map<String, String> preconfigParameters) {
        handleHistoryArguments(preconfigParameters);
    }

    @Override
    protected void setListener(TableSwitchListener listener) {
        super.setListener(listener);
        plot.setListener(listener);
    }
}
