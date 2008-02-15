package afeclient.client;

import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlowPanel;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Hyperlink;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.Widget;

/**
 * A widget to faciliate pagination of tables.  Shows currently displayed rows, 
 * total row count, and buttons for moving among pages.
 */
public class Paginator extends Composite {

    public interface PaginatorCallback {
        public void doRequest(int start);
    }
    
    class LinkWithDisable extends Composite {
        protected Panel panel = new FlowPanel();
        protected Label label;
        protected Hyperlink link;
        
        public LinkWithDisable(String text) {
            label = new Label(text);
            link = new SimpleHyperlink(text);
            panel.add(link);
            panel.add(label);
            link.setStyleName("paginator-link");
            label.setStyleName("paginator-link");
            initWidget(panel);
        }
        
        public void setEnabled(boolean enabled) {
            link.setVisible(enabled);
            label.setVisible(!enabled);
        }

        public void addClickListener(ClickListener listener) {
            link.addClickListener(listener);
        }

        public void removeClickListener(ClickListener listener) {
            link.removeClickListener(listener);
        }
    }

    protected int resultsPerPage, numTotalResults;
    protected PaginatorCallback callback;
    protected int currentStart = 0;

    protected HorizontalPanel mainPanel = new HorizontalPanel();
    protected LinkWithDisable nextControl, prevControl, 
                              firstControl, lastControl;
    protected Label statusLabel = new Label();

    public Paginator(int resultsPerPage, PaginatorCallback callback) {
        this.resultsPerPage = resultsPerPage;
        this.callback = callback;

        prevControl = new LinkWithDisable("< Previous");
        prevControl.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                currentStart -= Paginator.this.resultsPerPage;
                Paginator.this.callback.doRequest(currentStart);
                update();
            }
        });
        nextControl = new LinkWithDisable("Next >");
        nextControl.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                currentStart += Paginator.this.resultsPerPage;
                Paginator.this.callback.doRequest(currentStart);
                update();
            }
        });
        firstControl = new LinkWithDisable("<< First");
        firstControl.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                currentStart = 0;
                Paginator.this.callback.doRequest(currentStart);
                update();
            } 
        });
        lastControl = new LinkWithDisable("Last >>");
        lastControl.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                currentStart = getLastPageStart();
                Paginator.this.callback.doRequest(currentStart);
                update();
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
     * Set the total number of results in the current working set.
     */
    public void setNumTotalResults(int numResults) {
        this.numTotalResults = numResults;
        if (currentStart >= numResults)
            currentStart = getLastPageStart();
        update();
    }
    
    /**
     * Set the current starting index.
     */
    public void setStart(int start) {
        this.currentStart = start;
        update();
    }
    
    protected int getLastPageStart() {
        // compute start of last page using truncation
        return ((numTotalResults - 1) / resultsPerPage) * resultsPerPage;
    }

    protected void update() {
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
}
