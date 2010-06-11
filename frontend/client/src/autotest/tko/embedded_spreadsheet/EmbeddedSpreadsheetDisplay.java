package autotest.tko.embedded_spreadsheet;

import autotest.common.spreadsheet.Spreadsheet;

import com.google.gwt.dom.client.Element;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.SimplePanel;
import com.google.gwt.user.client.ui.Widget;

public class EmbeddedSpreadsheetDisplay extends Composite
        implements EmbeddedSpreadsheetPresenter.Display {
    private static final String NO_RESULTS = "There are no results for this query (yet?)";

    private Panel panel = new SimplePanel();
    private Spreadsheet spreadsheet = new Spreadsheet();
    private Label noResults = new Label(NO_RESULTS);

    public EmbeddedSpreadsheetDisplay() {
        initWidget(panel);
    }

    private void notifyParent(Widget w) {
        Element elem = w.getElement();
        notifyParent(elem.getClientWidth(), elem.getClientHeight());
    }

    private native void notifyParent(int width, int height) /*-{
        $wnd.parent.postMessage(width + 'px ' + height + 'px', '*');
    }-*/;

    @Override
    public Command getOnSpreadsheetRendered() {
        return new Command() {
            @Override
            public void execute() {
                notifyParent(spreadsheet);
            }
        };
    }

    @Override
    public Spreadsheet getSpreadsheet() {
        return spreadsheet;
    }

    @Override
    public void showNoResults() {
        panel.add(noResults);
        notifyParent(noResults);
    }

    @Override
    public void showSpreadsheet() {
        panel.add(spreadsheet);
    }
}
