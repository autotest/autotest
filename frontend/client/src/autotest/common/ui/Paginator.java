package autotest.common.ui;

import autotest.common.SimpleCallback;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlowPanel;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;

import java.util.ArrayList;
import java.util.List;

/**
 * A widget to faciliate pagination of tables.  Shows currently displayed rows,
 * total row count, and buttons for moving among pages.
 */
public class Paginator extends Composite {
    static class LinkWithDisable extends Composite {
        protected Panel panel = new FlowPanel();
        protected Label label;
        protected Anchor link;

        public LinkWithDisable(String text) {
            label = new Label(text);
            link = new Anchor(text);
            panel.add(link);
            panel.add(label);
            link.setStyleName("paginator-link");
            label.setStyleName("paginator-link");
            setEnabled(false); // default to not enabled
            initWidget(panel);
        }

        public void setEnabled(boolean enabled) {
            link.setVisible(enabled);
            label.setVisible(!enabled);
        }

        public void addClickHandler(ClickHandler handler) {
            link.addClickHandler(handler);
        }
    }

    protected int resultsPerPage, numTotalResults;
    protected List<SimpleCallback> callbacks = new ArrayList<SimpleCallback>();
    protected int currentStart = 0;

    protected HorizontalPanel mainPanel = new HorizontalPanel();
    protected LinkWithDisable nextControl, prevControl,
                              firstControl, lastControl;
    protected Label statusLabel = new Label();

    public Paginator() {
        prevControl = new LinkWithDisable("< Previous");
        prevControl.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                currentStart -= Paginator.this.resultsPerPage;
                notifyCallbacks();
            }
        });
        nextControl = new LinkWithDisable("Next >");
        nextControl.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                currentStart += Paginator.this.resultsPerPage;
                notifyCallbacks();
            }
        });
        firstControl = new LinkWithDisable("<< First");
        firstControl.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                currentStart = 0;
                notifyCallbacks();
            }
        });
        lastControl = new LinkWithDisable("Last >>");
        lastControl.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                currentStart = getLastPageStart();
                notifyCallbacks();
            }
        });

        statusLabel.setWidth("10em");
        statusLabel.setHorizontalAlignment(Label.ALIGN_CENTER);

        mainPanel.setVerticalAlignment(HorizontalPanel.ALIGN_MIDDLE);
        mainPanel.add(firstControl);
        mainPanel.add(prevControl);
        mainPanel.add(statusLabel);
        mainPanel.add(nextControl);
        mainPanel.add(lastControl);

        initWidget(mainPanel);
    }

    /**
     * Get the current starting row index.
     */
    public int getStart() {
        return currentStart;
    }

    /**
     * Get the current ending row index (one past the last currently displayed
     * row).
     */
    public int getEnd() {
        int end = currentStart + resultsPerPage;
        if (end < numTotalResults)
            return end;
        return numTotalResults;
    }

    /**
     * Get the size of each page.
     */
    public int getResultsPerPage() {
        return resultsPerPage;
    }

    /**
     * Set the size of a page.
     */
    public void setResultsPerPage(int resultsPerPage) {
        this.resultsPerPage = resultsPerPage;
    }

    /**
     * Set the total number of results in the current working set.
     */
    public void setNumTotalResults(int numResults) {
        this.numTotalResults = numResults;
        if (currentStart >= numResults)
            currentStart = getLastPageStart();
    }

    /**
     * Set the current starting index.
     */
    public void setStart(int start) {
        this.currentStart = start;
    }

    protected int getLastPageStart() {
        // compute start of last page using truncation
        return ((numTotalResults - 1) / resultsPerPage) * resultsPerPage;
    }

    public void update() {
        boolean prevEnabled = !(currentStart == 0);
        boolean nextEnabled = currentStart + resultsPerPage < numTotalResults;
        firstControl.setEnabled(prevEnabled);
        prevControl.setEnabled(prevEnabled);
        nextControl.setEnabled(nextEnabled);
        lastControl.setEnabled(nextEnabled);
        int displayStart = getStart() + 1;
        if(numTotalResults == 0)
            displayStart = 0;
        statusLabel.setText(displayStart + "-" + getEnd() +
                            " of " + numTotalResults);
    }

    public void addCallback(SimpleCallback callback) {
        callbacks.add(callback);
    }

    public void removeCallback(SimpleCallback callback) {
        callbacks.remove(callback);
    }

    protected void notifyCallbacks() {
        for (SimpleCallback callback : callbacks) {
            callback.doCallback(this);
        }
    }
}
