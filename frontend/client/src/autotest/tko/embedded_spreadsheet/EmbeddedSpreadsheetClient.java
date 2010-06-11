package autotest.tko.embedded_spreadsheet;

import com.google.gwt.core.client.EntryPoint;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.RootPanel;

public class EmbeddedSpreadsheetClient implements EntryPoint {
    private EmbeddedSpreadsheetPresenter presenter = new EmbeddedSpreadsheetPresenter();
    private EmbeddedSpreadsheetDisplay display = new EmbeddedSpreadsheetDisplay();

    @Override
    public void onModuleLoad() {
        presenter.bindDisplay(display);
        presenter.initialize(Window.Location.getParameter("afe_job_id"));
        RootPanel.get().add(display);
    }
}
